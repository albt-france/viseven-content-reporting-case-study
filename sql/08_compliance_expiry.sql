-- 08_compliance_expiry.sql: sessions started on a content after its MLR expiry or withdrawal (SIMULATED).
-- Reported to the client as an alert; it is not counted in the KPIs. No regulatory advice is given.
CREATE OR REPLACE TABLE out_compliance AS
SELECT f.content_id, c.market, c.brand, c.type, CAST(c.mlr_expiry AS DATE) AS mlr_expiry, f.status_at_event AS status,
       count(*) AS sessions, count(DISTINCT f.hcp_id) AS hcps, count(DISTINCT f.activity_id) FILTER (WHERE true) AS n_rows,
       CAST(min(f.ts) AS DATE) AS first_use_after_end, CAST(max(f.ts) AS DATE) AS last_use,
       max(date_diff('day', CAST(c.mlr_expiry AS DATE), CAST(f.ts AS DATE))) AS max_days_after_expiry
FROM fact_activity f JOIN dim_content c ON c.content_id = f.content_id
WHERE f.kind = 'session' AND f.status_at_event IN ('expired', 'withdrawn')
GROUP BY ALL ORDER BY sessions DESC;

-- weekly, so that no published bar describes fewer than 5 HCPs (weeks below 5 HCPs are dropped; checked by T04)
CREATE OR REPLACE TABLE out_compliance_weekly AS
SELECT CAST(date_trunc('week', f.ts) AS DATE) AS week, f.content_id, count(*) AS sessions, count(DISTINCT f.hcp_id) AS hcps
FROM fact_activity f WHERE f.kind = 'session' AND f.status_at_event IN ('expired', 'withdrawn')
GROUP BY ALL HAVING count(DISTINCT f.hcp_id) >= 5 ORDER BY 1, 2;
