-- 07_point_in_time_status.sql: the existing report filtered contents on their CURRENT status ('approved' today).
-- That silently drops all past activity of contents withdrawn or expired since, and rewrites past months each time a
-- content ends. Fix: join the status valid AT THE EVENT TIME (content_status.valid_from <= ts < valid_to). SIMULATED.
CREATE OR REPLACE TABLE out_point_in_time AS
SELECT month,
       count(*) FILTER (WHERE status_at_event = 'approved') AS sessions_point_in_time,
       count(*) FILTER (WHERE status_current = 'approved') AS sessions_current_status_filter,
       count(*) FILTER (WHERE status_at_event = 'approved') - count(*) FILTER (WHERE status_current = 'approved') AS sessions_erased,
       round(1 - count(*) FILTER (WHERE status_current = 'approved') / count(*) FILTER (WHERE status_at_event = 'approved'), 4) AS share_erased
FROM fact_activity WHERE kind = 'session' AND month BETWEEN '2025-12' AND '2026-11'
GROUP BY 1 ORDER BY 1;

-- The same month (March 2026) as the old logic would have published it at different dates
CREATE OR REPLACE TABLE out_point_in_time_restatement AS
WITH pub AS (SELECT unnest([DATE '2026-04-01', DATE '2026-07-01', DATE '2026-10-01', DATE '2026-11-25']) AS published_on)
SELECT a.published_on,
       (SELECT count(*) FROM fact_activity f JOIN content_status c ON c.content_id = f.content_id
         AND a.published_on >= c.valid_from AND a.published_on < c.valid_to
        WHERE f.kind = 'session' AND f.month = '2026-03' AND c.status = 'approved') AS march_sessions_current_status_logic,
       (SELECT count(*) FROM fact_activity f WHERE f.kind = 'session' AND f.month = '2026-03' AND f.status_at_event = 'approved') AS march_sessions_point_in_time
FROM pub a ORDER BY 1;

CREATE OR REPLACE TABLE out_contents_ended AS
SELECT count(*) FILTER (WHERE status = 'expired') AS expired, count(*) FILTER (WHERE status = 'withdrawn') AS withdrawn
FROM content_status WHERE status <> 'approved' AND valid_from BETWEEN TIMESTAMP '2025-12-01' AND TIMESTAMP '2026-11-25';
