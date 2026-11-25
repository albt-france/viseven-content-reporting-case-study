"""Verification checks on the loaded data (SIMULATED). Rules, thresholds and actions: docs/verification_rules.md.

C1 completeness  distinct event_ids per day of updated_at, warehouse vs the source's /v1/events/count (must be equal)
C2 uniqueness    event_id unique in raw_events; duplicates received and ignored by the loader (logged in load_runs)
C3 schema        required fields present, values in the allowed lists, timestamps parseable
C4 freshness     last updated_at loaded within 6 hours of the run clock (2026-11-25 00:00 UTC)
C5 time zone     timestamps without offset, by market (must be 0)
C6 sessions      session_end before its session_start when timestamps are read as written (must be 0)
C7 MLR expiry    sessions started on a content after its MLR expiry or withdrawal (must be 0; else alert the client)
C8 references    hcp_id / content_id unknown in the master data (must be 0)
    python src/verify.py --label before_backfill
Writes data/output/verification_checks.csv and data/output/reconciliation_daily.csv (one block per label).
"""
import argparse

import duckdb
import pandas as pd

from common import DB, OUT, SIM
from ingest import NOW, Client

TYPES = "('session_start','slide_view','session_end','email_sent','email_open','email_click','webinar_join')"
CHANNELS = "('e-detail','approved-email','webinar','web')"


def save(df, name, label):
    p = OUT / name
    df.insert(0, "run_label", label)
    if p.exists():
        old = pd.read_csv(p)
        df = pd.concat([old[old.run_label != label], df], ignore_index=True)
    df.to_csv(p, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="latest")
    label = ap.parse_args().label
    con = duckdb.connect(str(DB), read_only=True)
    con.execute(f"CREATE TEMP TABLE contents AS SELECT * FROM read_csv_auto('{(SIM / 'contents.csv').as_posix()}')")
    con.execute(f"CREATE TEMP TABLE hcps AS SELECT * FROM read_csv_auto('{(SIM / 'hcps.csv').as_posix()}')")
    checks = []

    def add(cid, rule, threshold, observed, ok, action, status_fail="FAIL"):
        checks.append({"check": cid, "rule": rule, "threshold": threshold, "observed": observed,
                       "status": "PASS" if ok else status_fail, "action": action})

    # C1 completeness against the source
    src = pd.DataFrame(Client().get("/v1/events/count", {"from": "", "to": NOW, "group_by": "day"})["days"])
    wh = con.execute("SELECT left(updated_at, 10) AS day, count(*) AS warehouse FROM raw_events GROUP BY 1").df()
    rec = src.merge(wh, on="day", how="outer").fillna(0)
    rec["gap"] = rec.warehouse - rec.distinct_event_ids
    rec = rec.sort_values("day")
    bad = rec[rec.gap != 0]
    add("C1", "distinct events per day = source /count", "0 days with a gap",
        f"{len(bad)} day(s), {int(bad.gap.sum())} events" + (f" (e.g. {bad.day.iloc[0]})" if len(bad) else ""), bad.empty,
        "find the window in load_runs, backfill it, re-run the checks")
    # C2 uniqueness
    dup_tab = con.execute("SELECT count(*) - count(DISTINCT event_id) FROM raw_events").fetchone()[0]
    dup_in = con.execute("SELECT coalesce(sum(duplicates_ignored), 0) FROM load_runs").fetchone()[0]
    add("C2", "event_id unique in the warehouse", "0 duplicates stored", f"{dup_tab} stored; {int(dup_in)} received and ignored",
        dup_tab == 0, "insert keyed on event_id; log the source duplicates in docs/data_issues_log.md")
    # C3 schema
    s = con.execute(f"""SELECT
        count(*) FILTER (WHERE event_id IS NULL OR event_ts IS NULL OR market IS NULL OR hcp_id IS NULL OR content_id IS NULL
                         OR channel IS NULL OR event_type IS NULL OR updated_at IS NULL) AS missing,
        count(*) FILTER (WHERE event_type NOT IN {TYPES} OR channel NOT IN {CHANNELS}) AS bad_values,
        count(*) FILTER (WHERE try_cast(replace(event_ts, 'Z', '') AS TIMESTAMP) IS NULL) AS bad_ts,
        count(*) FILTER (WHERE duration_s < 0) AS neg_duration FROM raw_events""").fetchone()
    add("C3", "required fields, allowed values, parseable timestamps", "0 rows", f"{s[0]} missing, {s[1]} bad values, {s[2]} bad timestamps, {s[3]} negative durations",
        sum(s) == 0, "quarantine the rows, ask the source owner")
    # C4 freshness
    lag = con.execute(f"SELECT date_diff('minute', max(cast(replace(updated_at,'Z','') AS TIMESTAMP)), TIMESTAMP '{NOW[:19].replace('T', ' ')}') FROM raw_events").fetchone()[0]
    add("C4", "last updated_at within 6 h of the run clock", "<= 360 min", f"{lag} min", lag <= 360, "check the scheduler and the API status")
    # C5 time zone
    tz = con.execute("SELECT market, count(*) n, min(left(event_ts, 10)) first_day FROM raw_events WHERE NOT event_ts LIKE '%Z' GROUP BY 1").df()
    add("C5", "every timestamp carries an offset (Z)", "0 rows",
        "; ".join(f"{r.market}: {r.n:,} rows from {r.first_day}" for r in tz.itertuples()) or "0", tz.empty,
        "read naive RO timestamps as Europe/Bucharest (sql/01_load.sql), ask the integration team to fix the version", "WARN")
    # C6 session coherence (as written)
    neg = con.execute("""
        WITH s AS (SELECT hcp_id, content_id, updated_at, try_cast(replace(event_ts,'Z','') AS TIMESTAMP) ts FROM raw_events WHERE event_type='session_start'),
             e AS (SELECT hcp_id, content_id, market, updated_at, try_cast(replace(event_ts,'Z','') AS TIMESTAMP) ts FROM raw_events WHERE event_type='session_end')
        SELECT e.market, count(*) n FROM e ASOF JOIN s ON e.hcp_id = s.hcp_id AND e.content_id = s.content_id AND e.updated_at >= s.updated_at
        WHERE e.ts < s.ts GROUP BY 1""").df()
    add("C6", "no session ends before it starts", "0 sessions",
        "; ".join(f"{r.market}: {r.n:,}" for r in neg.itertuples()) or "0", neg.empty, "same root cause as C5", "WARN")
    # C7 MLR expiry
    exp = con.execute("""
        SELECT r.content_id, c.market, c.brand, count(*) n, max(date_diff('day', least(c.mlr_expiry, coalesce(c.withdrawn, c.mlr_expiry)),
               cast(replace(r.updated_at,'Z','') AS TIMESTAMP))) max_days
        FROM raw_events r JOIN contents c USING (content_id)
        WHERE r.event_type = 'session_start' AND cast(replace(r.updated_at,'Z','') AS TIMESTAMP) >= least(c.mlr_expiry, coalesce(c.withdrawn, c.mlr_expiry))
        GROUP BY ALL ORDER BY 1""").df()
    add("C7", "no session on a content after its MLR expiry / withdrawal", "0 sessions",
        f"{int(exp.n.sum()) if len(exp) else 0} sessions on {len(exp)} content(s), up to {int(exp.max_days.max()) if len(exp) else 0} days late "
        + ", ".join(f"{r.content_id} {r.market} {r.brand}" for r in exp.itertuples()), exp.empty,
        "compliance alert in the report; raise with the client (no regulatory advice)", "ALERT")
    # C8 references
    ref = con.execute("""SELECT count(*) FILTER (WHERE h.hcp_id IS NULL), count(*) FILTER (WHERE c.content_id IS NULL)
        FROM raw_events r LEFT JOIN hcps h USING (hcp_id) LEFT JOIN contents c USING (content_id)""").fetchone()
    add("C8", "hcp_id and content_id exist in master data", "0 rows", f"{ref[0]} unknown HCP, {ref[1]} unknown content", sum(ref) == 0,
        "hold the rows, refresh the master data")
    ch = pd.DataFrame(checks)
    save(ch, "verification_checks.csv", label)
    save(rec[["day", "rows", "distinct_event_ids", "warehouse", "gap"]].copy(), "reconciliation_daily.csv", label)
    print(f"[{label}]", " | ".join(f"{r.check} {r.status}" for r in ch.itertuples()))
    for r in ch[ch.status != "PASS"].itertuples():
        print(f"  {r.check}: {r.observed}")


if __name__ == "__main__":
    main()
