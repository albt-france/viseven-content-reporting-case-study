-- 02_public_market.sql: the market these reports serve (PUBLIC DATA).
CREATE OR REPLACE TABLE out_physicians AS
SELECT p.market, p.year, CAST(p.physicians AS BIGINT) AS physicians, p.per_100k, m.target_hcps AS client_p_hcps_simulated
FROM read_csv_auto('data/public/eurostat_physicians.csv') p LEFT JOIN dim_market m USING (market)
ORDER BY physicians DESC;

-- EMA: human medicines still authorised, by year of authorisation and broad area. Survivor bias: medicines withdrawn
-- since are not in the 'Authorised' list, so older years are undercounted. Source: European Medicines Agency.
CREATE OR REPLACE TABLE out_ema_by_year_area AS
SELECT year(authorisation_date) AS year, area_group, count(*) AS medicines
FROM read_csv_auto('data/public/ema_medicines.csv')
WHERE category = 'Human' AND status = 'Authorised' AND authorisation_date >= DATE '2016-01-01'
GROUP BY ALL ORDER BY year, medicines DESC;

CREATE OR REPLACE TABLE out_ema_summary AS
SELECT count(*) FILTER (WHERE category = 'Human') AS human_rows,
       count(*) FILTER (WHERE category = 'Human' AND status = 'Authorised') AS human_authorised,
       count(*) FILTER (WHERE category = 'Human' AND status = 'Authorised' AND orphan = 'Yes') AS orphan_authorised,
       count(*) FILTER (WHERE category = 'Human' AND status = 'Authorised' AND biosimilar = 'Yes') AS biosimilar_authorised
FROM read_csv_auto('data/public/ema_medicines.csv');

-- ClinicalTrials.gov: recruiting studies with at least one site in the market (real REST load, totalCount checked)
CREATE OR REPLACE TABLE out_trials_by_market AS
WITH t AS (SELECT * FROM read_csv_auto('data/public/trials_recruiting.csv'))
SELECT t.market, count(DISTINCT nct_id) AS recruiting_studies,
       count(DISTINCT nct_id) FILTER (WHERE area = 'Oncology') AS oncology,
       round(100.0 * count(DISTINCT nct_id) FILTER (WHERE area = 'Oncology') / count(DISTINCT nct_id), 1) AS oncology_pct,
       any_value(l.total_count) AS api_total_count, any_value(l.received) AS received, any_value(l.complete) AS complete
FROM t JOIN read_csv_auto('data/public/trials_load_log.csv') l USING (market)
GROUP BY t.market ORDER BY recruiting_studies DESC;

CREATE OR REPLACE TABLE out_trials_by_area AS
SELECT market, area, count(DISTINCT nct_id) AS studies
FROM read_csv_auto('data/public/trials_recruiting.csv') GROUP BY ALL ORDER BY market, studies DESC;

-- npm: public activity index of the ewizard-cli package (downloads include bots and CI: not users, not clients)
CREATE OR REPLACE TABLE out_npm_monthly AS
SELECT strftime(CAST(day AS DATE), '%Y-%m') AS month, sum(downloads) AS downloads
FROM read_csv_auto('data/public/npm_ewizard_cli_downloads.csv') GROUP BY 1 ORDER BY 1;
