"""Load the Client P events from the local REST API into DuckDB (data/warehouse.duckdb, table raw_events). SIMULATED.

Modes
  --full                     full reload: everything with updated_at <= 2026-09-01 00:00 UTC (bulk pages of 5,000)
  --incremental [--job v1|v2]  replays the job scheduled every 6 h (03/09/15/21 UTC) from 01/09 to 25/11/2026
        v2 (default, the fix): the watermark moves only after a verified batch (rows received = /count for the window);
                               a failed run keeps the watermark and the next run picks the window up again.
        v1 (as found in production): the watermark moves to the run time even when the run failed -> reproduces
                               the 14/09/2026 incident (6 hours of data lost).
  --backfill --since <ISO> --until <ISO>   re-loads one window (idempotent), e.g. after an incident

Common rules: bearer token from .env; <= 4.5 requests/s; retries with exponential backoff on 5xx / network errors,
`Retry-After` respected on 429; idempotent insert keyed on event_id (duplicates are counted, never inserted twice).
Every run is logged in table load_runs.
    python src/ingest.py --full
    python src/ingest.py --incremental --job v1
    python src/ingest.py --backfill --since 2026-09-14T03:00:00Z --until 2026-09-14T09:00:00Z
"""
import argparse
import time

import duckdb
import pandas as pd
import requests

from common import API_HOST, API_PORT, DB, read_env

BASE = f"http://{API_HOST}:{API_PORT}"
FULL_AS_OF = "2026-09-01T00:00:00Z"
NOW = "2026-11-25T00:00:00Z"
COLS = ["event_id", "event_ts", "market", "hcp_id", "content_id", "channel", "event_type", "duration_s", "rep_id", "updated_at"]
DDL = """
CREATE TABLE IF NOT EXISTS raw_events (event_id VARCHAR PRIMARY KEY, event_ts VARCHAR, market VARCHAR, hcp_id VARCHAR,
  content_id VARCHAR, channel VARCHAR, event_type VARCHAR, duration_s DOUBLE, rep_id VARCHAR, updated_at VARCHAR, load_id INTEGER);
CREATE TABLE IF NOT EXISTS load_state (job VARCHAR PRIMARY KEY, watermark VARCHAR);
CREATE TABLE IF NOT EXISTS load_runs (run_id INTEGER, job VARCHAR, mode VARCHAR, as_of VARCHAR, updated_since VARCHAR,
  updated_until VARCHAR, requests INTEGER, http_429 INTEGER, http_5xx INTEGER, rows_received INTEGER, rows_inserted INTEGER,
  duplicates_ignored INTEGER, source_count INTEGER, status VARCHAR, watermark_after VARCHAR, seconds DOUBLE);
"""


class Client:
    def __init__(self, min_interval=0.22):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {read_env().get('MOCK_API_TOKEN', '')}"
        self.min_interval, self.last = min_interval, 0.0
        self.n = self.n429 = self.n5xx = 0

    def get(self, path, params, attempts=5):
        for k in range(attempts):
            wait = self.min_interval - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.n += 1
            try:
                r = self.s.get(BASE + path, params=params, timeout=30)
            except requests.RequestException:
                time.sleep(0.5 * 2 ** k)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                self.n429 += 1
                time.sleep(float(r.headers.get("Retry-After", 1)))
                continue
            if r.status_code >= 500:
                self.n5xx += 1
                time.sleep(0.5 * 2 ** k)              # 0.5, 1, 2, 4, 8 s
                continue
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        raise ConnectionError(f"{path} failed after {attempts} attempts")

    def window(self, since, until, as_of, limit):
        rows, cursor = [], None
        while True:
            p = {"updated_since": since, "updated_until": until, "as_of": as_of, "limit": limit}
            if cursor:
                p["cursor"] = cursor
            j = self.get("/v1/events", p)
            rows.extend(j["data"])
            cursor = j["next_cursor"]
            if not cursor:
                return rows


def connect():
    con = duckdb.connect(str(DB))
    con.execute(DDL)
    return con


def insert(con, rows, load_id):
    if not rows:
        return 0, 0
    df = pd.DataFrame(rows)[COLS]
    within = int(df.event_id.duplicated().sum())
    df = df.drop_duplicates("event_id")
    df["load_id"] = load_id
    before = con.execute("SELECT count(*) FROM raw_events").fetchone()[0]
    con.execute("INSERT OR IGNORE INTO raw_events SELECT * FROM df")
    ins = con.execute("SELECT count(*) FROM raw_events").fetchone()[0] - before
    return ins, within + (len(df) - ins)


def log(con, **r):
    rid = con.execute("SELECT coalesce(max(run_id), 0) + 1 FROM load_runs").fetchone()[0]
    cols = ["job", "mode", "as_of", "updated_since", "updated_until", "requests", "http_429", "http_5xx", "rows_received",
            "rows_inserted", "duplicates_ignored", "source_count", "status", "watermark_after", "seconds"]
    con.execute(f"INSERT INTO load_runs VALUES ({', '.join(['?'] * 16)})", [rid] + [r.get(c) for c in cols])
    return rid


def run_window(con, cl, job, mode, since, until, as_of, limit, verify):
    t0, n0, a0, b0 = time.time(), cl.n, cl.n429, cl.n5xx
    rid = con.execute("SELECT coalesce(max(run_id), 0) + 1 FROM load_runs").fetchone()[0]
    rec = dict(job=job, mode=mode, as_of=as_of, updated_since=since, updated_until=until)
    try:
        rows = cl.window(since, until, as_of, limit)
        src = cl.get("/v1/events/count", {"from": since, "to": until})["rows"] if verify else None
        if verify and src != len(rows):
            raise ValueError(f"batch not verified: received {len(rows)} rows, source counts {src}")
        con.execute("BEGIN")
        ins, dup = insert(con, rows, rid)
        con.execute("COMMIT")
        rec.update(rows_received=len(rows), rows_inserted=ins, duplicates_ignored=dup, source_count=src, status="ok")
    except (ConnectionError, ValueError, RuntimeError) as e:
        rec.update(rows_received=0, rows_inserted=0, duplicates_ignored=0, status=f"failed: {str(e)[:80]}")
    rec.update(requests=cl.n - n0, http_429=cl.n429 - a0, http_5xx=cl.n5xx - b0, seconds=round(time.time() - t0, 2))
    return rec


def set_wm(con, job, wm):
    con.execute("INSERT OR REPLACE INTO load_state VALUES (?, ?)", [job, wm])


def full(con, cl):
    con.execute("DELETE FROM raw_events; DELETE FROM load_state; DELETE FROM load_runs;")
    rec = run_window(con, cl, "full", "full", "", FULL_AS_OF, FULL_AS_OF, 5000, verify=True)
    if rec["status"] == "ok":
        for j in ("v1", "v2"):
            set_wm(con, j, FULL_AS_OF)
    rec["watermark_after"] = FULL_AS_OF
    log(con, **rec)
    print("full", rec["status"], rec["rows_inserted"], "rows,", rec["requests"], "requests,", rec["seconds"], "s")


def schedule(start, end):
    t = pd.Timestamp(start)
    out = []
    while t <= pd.Timestamp(end):
        if t.hour in (3, 9, 15, 21) or t == pd.Timestamp(end):
            out.append(t.strftime("%Y-%m-%dT%H:%M:%SZ"))
        t += pd.Timedelta(hours=1)
    return out


def incremental(con, cl, job, start=FULL_AS_OF, end=NOW, quiet=False):
    wm = con.execute("SELECT watermark FROM load_state WHERE job = ?", [job]).fetchone()[0]
    runs = [r for r in schedule(start, end) if r > wm]
    fails = 0
    for as_of in runs:
        wm = con.execute("SELECT watermark FROM load_state WHERE job = ?", [job]).fetchone()[0]
        rec = run_window(con, cl, job, "incremental", wm, as_of, as_of, 500, verify=(job == "v2"))
        ok = rec["status"] == "ok"
        new = as_of if (ok or job == "v1") else wm          # v1 bug: moves on even after a failed run
        set_wm(con, job, new)
        rec["watermark_after"] = new
        log(con, **rec)
        if not ok:
            fails += 1
            if not quiet:
                print(f"  run {as_of} {rec['status']} -> watermark {'ADVANCED (data lost)' if job == 'v1' else 'kept'} at {new}")
    if not quiet:
        tot = con.execute("SELECT sum(rows_inserted), sum(duplicates_ignored), sum(requests) FROM load_runs WHERE mode='incremental' AND job=?", [job]).fetchone()
        print(f"incremental job {job}: {len(runs)} runs, {fails} failed, {tot[0]} rows inserted, {tot[1]} duplicates ignored, {tot[2]} requests")


def backfill(con, cl, since, until):
    rec = run_window(con, cl, "backfill", "backfill", since, until, NOW, 500, verify=True)
    rec["watermark_after"] = None
    log(con, **rec)
    print("backfill", since, "->", until, rec["status"], rec["rows_received"], "received,", rec["rows_inserted"], "inserted,",
          rec["duplicates_ignored"], "already present")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--full", action="store_true")
    g.add_argument("--incremental", action="store_true")
    g.add_argument("--backfill", action="store_true")
    ap.add_argument("--job", choices=["v1", "v2"], default="v2")
    ap.add_argument("--since")
    ap.add_argument("--until")
    a = ap.parse_args()
    con, cl = connect(), Client()
    cl.get("/v1/events/count", {"from": NOW, "to": NOW})       # fail fast if the API is not running
    if a.full:
        full(con, cl)
    elif a.incremental:
        incremental(con, cl, a.job)
    else:
        backfill(con, cl, a.since, a.until)
    con.close()


if __name__ == "__main__":
    main()
