-- 05_verification.sql: the verification checks of src/verify.py, re-derived in SQL (SIMULATED).
CREATE OR REPLACE TABLE out_load_runs AS
SELECT job, mode, count(*) AS runs, count(*) FILTER (WHERE status LIKE 'failed%') AS failed_runs,
       sum(requests) AS requests, sum(http_5xx) AS http_5xx, sum(http_429) AS http_429,
       sum(rows_received) AS rows_received, sum(rows_inserted) AS rows_inserted, sum(duplicates_ignored) AS duplicates_ignored,
       round(sum(seconds), 1) AS seconds
FROM load_runs GROUP BY ALL ORDER BY min(run_id);

CREATE OR REPLACE TABLE out_failed_runs AS
SELECT run_id, job, as_of, updated_since, status, watermark_after FROM load_runs WHERE status LIKE 'failed%';

-- daily reconciliation written by verify.py (source /count vs warehouse), around the incident
CREATE OR REPLACE TABLE out_reconciliation_incident AS
SELECT run_label, day, distinct_event_ids AS source_events, warehouse AS warehouse_events, gap
FROM read_csv_auto('data/output/reconciliation_daily.csv')
WHERE day BETWEEN '2026-09-12' AND '2026-09-16' ORDER BY run_label DESC, day;

-- time zone: naive timestamps, and sessions ending before they start, as written vs after the fix of 01_load.sql
CREATE OR REPLACE TABLE out_timezone_check AS
WITH s AS (
  SELECT e.market, e.hcp_id, e.content_id, e.updated_at,
         e.ts_written AS end_written, e.event_ts_utc AS end_fixed FROM stg_events e WHERE event_type = 'session_end'),
st AS (SELECT market, hcp_id, content_id, updated_at, ts_written, event_ts_utc FROM stg_events WHERE event_type = 'session_start'),
j AS (SELECT s.market, s.end_written < st.ts_written AS neg_written, s.end_fixed < st.event_ts_utc AS neg_fixed
      FROM s ASOF JOIN st ON s.hcp_id = st.hcp_id AND s.content_id = st.content_id AND s.updated_at >= st.updated_at)
SELECT j.market, count(*) AS sessions, count(*) FILTER (WHERE neg_written) AS end_before_start_as_written,
       count(*) FILTER (WHERE neg_fixed) AS end_before_start_after_fix,
       (SELECT count(*) FROM stg_events n WHERE n.naive_ts AND n.market = j.market) AS naive_timestamps
FROM j GROUP BY 1 ORDER BY 1;

-- RO: hour of session_start (UTC), September (before the integration change) vs October-November as written and fixed
CREATE OR REPLACE TABLE out_ro_hour_profile AS
SELECT hour(ts) AS hour_utc, version, count(*) AS sessions, count(DISTINCT hcp_id) AS hcps FROM (
  SELECT ts_written AS ts, hcp_id, 'Sep 2026' AS version FROM stg_events
   WHERE market = 'RO' AND event_type = 'session_start' AND channel = 'e-detail' AND strftime(event_ts_utc, '%Y-%m') = '2026-09'
  UNION ALL
  SELECT ts_written, hcp_id, 'Oct-Nov as written' FROM stg_events
   WHERE market = 'RO' AND event_type = 'session_start' AND channel = 'e-detail' AND event_ts_utc >= TIMESTAMP '2026-10-01'
  UNION ALL
  SELECT event_ts_utc, hcp_id, 'Oct-Nov fixed' FROM stg_events
   WHERE market = 'RO' AND event_type = 'session_start' AND channel = 'e-detail' AND event_ts_utc >= TIMESTAMP '2026-10-01')
GROUP BY ALL HAVING count(DISTINCT hcp_id) >= 5 ORDER BY version, hour_utc;   -- hours with fewer than 5 HCPs are not published

CREATE OR REPLACE TABLE out_verification_sql AS
SELECT 'event_id unique' AS check_name, (SELECT count(*) - count(DISTINCT event_id) FROM raw_events) AS observed, 0 AS expected
UNION ALL SELECT 'duplicates received and ignored', (SELECT sum(duplicates_ignored) FROM load_runs), NULL
UNION ALL SELECT 'days with a gap, before backfill', (SELECT count(*) FROM read_csv_auto('data/output/reconciliation_daily.csv') WHERE run_label = 'before_backfill' AND gap <> 0), NULL
UNION ALL SELECT 'days with a gap, after backfill', (SELECT count(*) FROM read_csv_auto('data/output/reconciliation_daily.csv') WHERE run_label = 'after_backfill' AND gap <> 0), 0
UNION ALL SELECT 'naive timestamps', (SELECT count(*) FROM stg_events WHERE naive_ts), NULL
UNION ALL SELECT 'sessions ending before start, after fix', (SELECT sum(end_before_start_after_fix) FROM out_timezone_check), 0
UNION ALL SELECT 'sessions without session_end (overlapping sessions, see data_issues_log)', (SELECT count(*) FROM sessions WHERE end_ts IS NULL), NULL
UNION ALL SELECT 'events on unknown HCP or content', (SELECT count(*) FROM stg_events e WHERE e.hcp_id NOT IN (SELECT hcp_id FROM dim_hcp)
                                                        OR e.content_id NOT IN (SELECT content_id FROM dim_content)), 0;
