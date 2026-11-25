-- 03_sessions.sql: sessionisation of e-detail and web events (SIMULATED).
-- A session = the events of one HCP on one content from a session_start to the next session_start.
-- Engagement time, capped (docs/kpi_definitions.md): from session_start to min(session_end, last slide_view + 30 s),
-- minus the part of any gap between two slide views above 30 minutes. Naive = duration reported by session_end.
CREATE OR REPLACE TABLE sessions AS
WITH e AS (
  SELECT *, sum(CASE WHEN event_type = 'session_start' THEN 1 ELSE 0 END) OVER (
              PARTITION BY hcp_id, content_id ORDER BY event_ts_utc,
              CASE event_type WHEN 'session_start' THEN 0 WHEN 'slide_view' THEN 1 ELSE 2 END, event_id) AS sess_no
  FROM stg_events WHERE channel IN ('e-detail', 'web')),
g AS (
  SELECT *, event_ts_utc - lag(event_ts_utc) OVER (PARTITION BY hcp_id, content_id, sess_no ORDER BY event_ts_utc, event_id) AS gap
  FROM e WHERE event_type = 'slide_view'),
long_gaps AS (
  SELECT hcp_id, content_id, sess_no, sum(greatest(epoch(gap) - 1800, 0)) AS cut_s FROM g GROUP BY ALL),
s AS (
  SELECT hcp_id, content_id, sess_no, any_value(market) AS market, any_value(channel) AS channel, any_value(rep_id) AS rep_id,
         min(event_ts_utc) FILTER (WHERE event_type = 'session_start') AS start_ts,
         max(event_ts_utc) FILTER (WHERE event_type = 'session_end') AS end_ts,
         max(event_ts_utc) FILTER (WHERE event_type = 'slide_view') AS last_slide_ts,
         count(*) FILTER (WHERE event_type = 'slide_view') AS slides,
         max(duration_s) FILTER (WHERE event_type = 'session_end') AS naive_s
  FROM e GROUP BY ALL)
SELECT s.hcp_id || '-' || s.content_id || '-' || s.sess_no AS session_id, s.*,
       CAST(start_ts AS DATE) AS session_date, strftime(start_ts, '%Y-%m') AS month,
       epoch(least(end_ts, last_slide_ts + INTERVAL 30 SECOND) - start_ts) - coalesce(l.cut_s, 0) AS capped_s,
       epoch(end_ts - last_slide_ts) > 1800 AS idle_tail
FROM s LEFT JOIN long_gaps l USING (hcp_id, content_id, sess_no)
WHERE start_ts IS NOT NULL;

CREATE OR REPLACE TABLE out_engagement_definition AS
SELECT channel, count(*) AS sessions, count(*) FILTER (WHERE idle_tail) AS idle_sessions,
       round(sum(naive_s) / count(*) / 60, 2) AS naive_min_per_session,
       round(sum(capped_s) / count(*) / 60, 2) AS capped_min_per_session,
       round(sum(naive_s) / sum(capped_s) - 1, 4) AS naive_inflation
FROM sessions GROUP BY 1 ORDER BY 1;

CREATE OR REPLACE TABLE out_engagement_monthly AS
SELECT month, round(sum(naive_s) / count(*) / 60, 2) AS naive_min, round(sum(capped_s) / count(*) / 60, 2) AS capped_min
FROM sessions WHERE channel = 'e-detail' GROUP BY 1 ORDER BY 1;
