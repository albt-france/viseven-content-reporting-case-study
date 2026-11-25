-- 01_load.sql: master data, public files and the staging table of events (SIMULATED + PUBLIC).
-- Raw events are loaded by src/ingest.py into raw_events (one row per event_id, insert keyed on event_id).
CREATE OR REPLACE TABLE dim_market AS SELECT * FROM read_csv_auto('data/sim/markets.csv');
CREATE OR REPLACE TABLE dim_hcp AS SELECT * FROM read_csv_auto('data/sim/hcps.csv');
CREATE OR REPLACE TABLE dim_content AS SELECT * FROM read_csv_auto('data/sim/contents.csv');
CREATE OR REPLACE TABLE content_status AS SELECT * FROM read_csv_auto('data/sim/content_status_history.csv');
CREATE OR REPLACE TABLE dim_brand AS SELECT * FROM read_csv_auto('data/sim/brands.csv');
CREATE OR REPLACE TABLE prior_year AS SELECT * FROM read_csv_auto('data/sim/prior_year_monthly.csv');
CREATE OR REPLACE TABLE holidays AS SELECT market, CAST(date AS DATE) AS d, name FROM read_csv_auto('data/public/holidays.csv');

-- Staging: timestamps as UTC TIMESTAMP. Since 01/10/2026 the RO device integration writes session_start / slide_view
-- in local time WITHOUT offset. Fix: of the two possible UTC readings (local - 3 h in summer, local - 2 h in winter,
-- Europe/Bucharest), keep the one that is not after the server receive time updated_at and closest to it.
-- This also handles the change of offset on 25/10/2026 (DST end), where a fixed -3 h would be wrong by 1 hour.
CREATE OR REPLACE TABLE stg_events AS
WITH r AS (
  SELECT *, CAST(replace(updated_at, 'Z', '') AS TIMESTAMP) AS upd,
         CAST(replace(event_ts, 'Z', '') AS TIMESTAMP) AS ts_written,
         NOT event_ts LIKE '%Z' AS naive_ts
  FROM raw_events)
SELECT event_id, market, hcp_id, content_id, channel, event_type, duration_s, rep_id, upd AS updated_at, naive_ts, ts_written,
       CASE WHEN NOT naive_ts THEN ts_written
            WHEN ts_written - INTERVAL 2 HOUR <= upd THEN ts_written - INTERVAL 2 HOUR
            ELSE ts_written - INTERVAL 3 HOUR END AS event_ts_utc
FROM r;
