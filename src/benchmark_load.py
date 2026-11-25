"""Measure the load procedures against the local API (SIMULATED). Every number is measured on this machine, not estimated.

Scenarios (each in its own scratch DuckDB file, deleted afterwards):
  full_500        full reload of the whole year, pages of 500 rows
  full_5000       full reload of the whole year, pages of 5,000 rows (proposed optimisation for full reloads)
  incremental_day one day of the 6-hourly incremental job (4 runs), pages of 500
  incident_v1     14/09/2026 replayed with job v1 (watermark moves after a failed run)
  incident_v2     14/09/2026 replayed with job v2 (watermark moves only after a verified batch)
Output: data/output/benchmark_load.csv
    python src/benchmark_load.py        (the API must be running)
"""
import time

import duckdb
import pandas as pd

from common import OUT, ROOT
from ingest import DDL, NOW, Client, incremental, run_window, set_wm

TMP = ROOT / "data" / "_bench.duckdb"


def fresh():
    for p in (TMP, TMP.with_suffix(".duckdb.wal")):
        p.unlink(missing_ok=True)
    con = duckdb.connect(str(TMP))
    con.execute(DDL)
    return con


def total(con):
    return con.execute("SELECT count(*) FROM raw_events").fetchone()[0]


def full(limit):
    con, cl = fresh(), Client()
    t0 = time.time()
    rec = run_window(con, cl, "bench", "full", "", NOW, NOW, limit, verify=True)
    out = {"requests": rec["requests"], "seconds": round(time.time() - t0, 1), "rows_loaded": total(con), "lost_events": 0}
    con.close()
    return out


def preload(until):
    con, cl = fresh(), Client()
    run_window(con, cl, "bench", "full", "", until, NOW, 5000, verify=True)
    for j in ("v1", "v2"):
        set_wm(con, j, until)
    return con, cl


def incr_day():
    con, cl = preload("2026-11-23T21:00:00Z")
    n0, r0, t0 = cl.n, total(con), time.time()
    incremental(con, cl, "v2", "2026-11-24T00:00:00Z", "2026-11-24T21:00:00Z", quiet=True)
    out = {"requests": cl.n - n0, "seconds": round(time.time() - t0, 1), "rows_loaded": total(con) - r0, "lost_events": 0}
    con.close()
    return out


def incident(job):
    start, end = "2026-09-14T03:00:00Z", "2026-09-15T03:00:00Z"
    con, cl = preload(start)
    n0, r0, t0 = cl.n, total(con), time.time()
    incremental(con, cl, job, "2026-09-14T04:00:00Z", end, quiet=True)
    loaded = total(con) - r0
    src = cl.get("/v1/events/count", {"from": start, "to": end})["distinct_event_ids"]
    failed = con.execute("SELECT count(*) FROM load_runs WHERE status LIKE 'failed%'").fetchone()[0]
    out = {"requests": cl.n - n0, "seconds": round(time.time() - t0, 1), "rows_loaded": loaded, "lost_events": src - loaded,
           "failed_runs": failed}
    con.close()
    return out


def main():
    rows = []
    for name, f, note in [
        ("full_500", lambda: full(500), "whole year, 500 rows per page"),
        ("full_5000", lambda: full(5000), "whole year, 5,000 rows per page"),
        ("incremental_day", incr_day, "24/11/2026, 4 runs, 500 rows per page"),
        ("incident_v1", lambda: incident("v1"), "14/09/2026 03:00 -> 15/09 03:00, watermark moves after failure"),
        ("incident_v2", lambda: incident("v2"), "14/09/2026 03:00 -> 15/09 03:00, watermark moves after verified batch")]:
        r = {"scenario": name, **f(), "note": note}
        rows.append(r)
        print(name, {k: v for k, v in r.items() if k != "note"})
    d = pd.DataFrame(rows)
    d["rows_per_request"] = (d.rows_loaded / d.requests).round(0)
    d.to_csv(OUT / "benchmark_load.csv", index=False)
    for p in (TMP, TMP.with_suffix(".duckdb.wal")):
        p.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
