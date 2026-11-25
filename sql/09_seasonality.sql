-- 09_seasonality.sql: is the August dip a tracking failure? Compare with working days and with the prior year.
-- Working day = Monday-Friday and not a national public holiday of the market (Nager.Date). SIMULATED + PUBLIC.
CREATE OR REPLACE TABLE working_days AS
WITH d AS (SELECT CAST(unnest(generate_series(DATE '2025-06-01', DATE '2026-11-24', INTERVAL 1 DAY)) AS DATE) AS d),
m AS (SELECT market FROM dim_market)
SELECT m.market, strftime(d.d, '%Y-%m') AS month,
       count(*) FILTER (WHERE isodow(d.d) <= 5 AND h.d IS NULL) AS working_days
FROM d CROSS JOIN m LEFT JOIN holidays h ON h.market = m.market AND h.d = d.d
GROUP BY ALL;

CREATE OR REPLACE TABLE out_seasonality AS
WITH s AS (
  SELECT month, market, count(*) AS edetail_sessions, 'event data' AS source FROM sessions WHERE channel = 'e-detail' GROUP BY ALL
  UNION ALL
  SELECT month, market, edetail_sessions, 'prior-year report' FROM prior_year)
SELECT s.month, s.source, sum(s.edetail_sessions) AS edetail_sessions, sum(w.working_days) AS market_working_days,
       round(sum(s.edetail_sessions) / sum(w.working_days), 3) AS sessions_per_market_working_day
FROM s JOIN working_days w USING (month, market)
GROUP BY ALL ORDER BY 1;

CREATE OR REPLACE TABLE out_august_check AS
WITH x AS (SELECT left(month, 4) AS year, month, edetail_sessions, sessions_per_market_working_day AS per_wd FROM out_seasonality
           WHERE month IN ('2025-07', '2025-08', '2026-07', '2026-08'))
SELECT j.year, j.edetail_sessions AS july, a.edetail_sessions AS august,
       round(a.edetail_sessions / j.edetail_sessions - 1, 4) AS change,
       round(a.per_wd / j.per_wd - 1, 4) AS change_per_working_day
FROM x j JOIN x a ON a.year = j.year AND a.month = j.year || '-08' WHERE j.month = j.year || '-07' ORDER BY 1;

-- public holidays falling on a working day, July-August and December-January (8 markets)
CREATE OR REPLACE TABLE out_holidays_summer_winter AS
SELECT market, strftime(d, '%Y-%m') AS month, count(*) AS weekday_holidays
FROM holidays WHERE isodow(d) <= 5 AND month(d) IN (7, 8, 12, 1) AND d BETWEEN DATE '2025-07-01' AND DATE '2026-08-31'
GROUP BY ALL ORDER BY 2, 1;
