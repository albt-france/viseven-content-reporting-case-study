-- 04_kpi.sql: monthly content-engagement KPIs of Client P (SIMULATED). Definitions: docs/kpi_definitions.md.
-- Activity counts only when the content was MLR-approved AT THE TIME of the event (point-in-time status, see 07).
CREATE OR REPLACE TABLE fact_activity AS
WITH a AS (
  SELECT session_id AS activity_id, market, hcp_id, content_id, channel, start_ts AS ts, 'session' AS kind, capped_s, naive_s
  FROM sessions
  UNION ALL
  SELECT event_id, market, hcp_id, content_id, channel, event_ts_utc,
         CASE event_type WHEN 'email_sent' THEN 'sent' WHEN 'email_open' THEN 'open' WHEN 'email_click' THEN 'click' ELSE 'join' END,
         NULL, NULL
  FROM stg_events WHERE event_type IN ('email_sent', 'email_open', 'email_click', 'webinar_join'))
SELECT a.*, strftime(a.ts, '%Y-%m') AS month, h.specialty AS segment,
       coalesce(cs.status, 'not yet approved') AS status_at_event, coalesce(cur.status, 'not yet approved') AS status_current
FROM a JOIN dim_hcp h ON h.hcp_id = a.hcp_id
LEFT JOIN content_status cs ON cs.content_id = a.content_id AND a.ts >= cs.valid_from AND a.ts < cs.valid_to
LEFT JOIN content_status cur ON cur.content_id = a.content_id
      AND TIMESTAMP '2026-11-25 00:00:00' >= cur.valid_from AND TIMESTAMP '2026-11-25 00:00:00' < cur.valid_to;

-- Published cells: month x market x channel x segment, plus 'All' rows (distinct HCP counts are not additive).
CREATE OR REPLACE TABLE report_cells AS
SELECT month, market, coalesce(channel, 'All') AS channel, coalesce(segment, 'All') AS segment,
       count(DISTINCT hcp_id) AS hcps_active,
       count(DISTINCT hcp_id) FILTER (WHERE kind IN ('session', 'open', 'join')) AS hcps_reached,
       count(*) FILTER (WHERE kind = 'session') AS sessions,
       coalesce(sum(capped_s), 0) AS engaged_s,
       coalesce(sum(naive_s), 0) AS naive_s,
       count(*) FILTER (WHERE kind = 'sent') AS emails_sent,
       count(*) FILTER (WHERE kind = 'open') AS emails_opened,
       count(*) FILTER (WHERE kind = 'click') AS emails_clicked,
       count(*) FILTER (WHERE kind = 'join') AS webinar_joins
FROM fact_activity
WHERE status_at_event = 'approved' AND month BETWEEN '2025-12' AND '2026-11'
GROUP BY GROUPING SETS ((month, market, channel, segment), (month, market, segment), (month, market, channel), (month, market));

-- Small-group rule: no published cell about 1 to 4 HCPs. Primary suppression, then secondary suppression of the
-- smallest other segment of the same month x market x channel, so the small cell cannot be rebuilt by subtraction.
CREATE OR REPLACE TABLE out_report_monthly AS
WITH t AS (SELECT market, specialty AS segment, count(*) AS hcps_targeted FROM dim_hcp GROUP BY ROLLUP (market, specialty)),
p AS (SELECT *, hcps_active BETWEEN 1 AND 4 AS primary_sup FROM report_cells),
g AS (SELECT month, market, channel, count(*) FILTER (WHERE primary_sup) AS n_sup FROM p WHERE segment <> 'All' GROUP BY ALL),
r AS (SELECT p.*, row_number() OVER (PARTITION BY p.month, p.market, p.channel ORDER BY p.primary_sup, p.hcps_active) AS rk
      FROM p WHERE p.segment <> 'All' AND NOT p.primary_sup),
s AS (
  SELECT p.*, p.primary_sup OR (p.segment <> 'All' AND g.n_sup = 1 AND r.rk = 1) AS suppressed
  FROM p LEFT JOIN g USING (month, market, channel)
  LEFT JOIN r ON r.month = p.month AND r.market = p.market AND r.channel = p.channel AND r.segment = p.segment)
SELECT s.month, s.market, s.channel, s.segment, coalesce(t.hcps_targeted, 0) AS hcps_targeted, s.suppressed,
       CASE WHEN s.suppressed THEN NULL ELSE s.hcps_active END AS hcps_active,
       CASE WHEN s.suppressed THEN NULL ELSE s.hcps_reached END AS hcps_reached,
       CASE WHEN s.suppressed THEN NULL ELSE s.sessions END AS sessions,
       CASE WHEN s.suppressed THEN NULL ELSE s.engaged_s END AS engaged_s,
       CASE WHEN s.suppressed THEN NULL ELSE s.naive_s END AS naive_s,
       CASE WHEN s.suppressed THEN NULL ELSE s.emails_sent END AS emails_sent,
       CASE WHEN s.suppressed THEN NULL ELSE s.emails_opened END AS emails_opened,
       CASE WHEN s.suppressed THEN NULL ELSE s.emails_clicked END AS emails_clicked,
       CASE WHEN s.suppressed THEN NULL ELSE s.webinar_joins END AS webinar_joins
FROM s LEFT JOIN t ON t.market = s.market AND t.segment IS NOT DISTINCT FROM (CASE WHEN s.segment = 'All' THEN NULL ELSE s.segment END)
ORDER BY 1, 2, 3, 4;

-- Headline KPIs by month and market (the report's first table)
CREATE OR REPLACE TABLE out_kpi_market AS
WITH a AS (SELECT * FROM out_report_monthly WHERE segment = 'All')
SELECT x.month, x.market, x.hcps_targeted, x.hcps_reached,
       round(x.hcps_reached / x.hcps_targeted, 4) AS coverage,
       round((x.sessions + x.emails_opened + x.webinar_joins) / x.hcps_reached, 3) AS frequency,
       d.sessions AS edetail_sessions,
       round(d.engaged_s / d.sessions / 60, 3) AS engaged_min_per_session,
       round(d.naive_s / d.sessions / 60, 3) AS naive_min_per_session,
       e.emails_sent, round(e.emails_opened / e.emails_sent, 4) AS open_rate, round(e.emails_clicked / e.emails_sent, 4) AS ctr,
       w.webinar_joins
FROM a x
LEFT JOIN a d ON d.month = x.month AND d.market = x.market AND d.channel = 'e-detail'
LEFT JOIN a e ON e.month = x.month AND e.market = x.market AND e.channel = 'approved-email'
LEFT JOIN a w ON w.month = x.month AND w.market = x.market AND w.channel = 'webinar'
WHERE x.channel = 'All'
ORDER BY 1, 2;

CREATE OR REPLACE TABLE out_kpi_total AS
SELECT month, sum(hcps_reached) AS hcps_reached, sum(hcps_targeted) AS hcps_targeted, sum(edetail_sessions) AS edetail_sessions,
       sum(emails_sent) AS emails_sent, sum(webinar_joins) AS webinar_joins
FROM out_kpi_market GROUP BY 1 ORDER BY 1;
