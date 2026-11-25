-- 99_tests.sql: assertions on the warehouse and the published outputs. result = PASS / FAIL / SKIP.
CREATE OR REPLACE TABLE test_results (test VARCHAR, result VARCHAR, detail VARCHAR);

-- keys
INSERT INTO test_results SELECT 'T01 event_id unique after de-duplication',
  CASE WHEN count(*) = count(DISTINCT event_id) THEN 'PASS' ELSE 'FAIL' END, count(*) || ' events' FROM stg_events;

-- report totals = sum of markets (and = the activity base)
INSERT INTO test_results
WITH m AS (SELECT month, sum(sessions) s, sum(emails_sent) e, sum(webinar_joins) w FROM out_report_monthly
           WHERE channel = 'All' AND segment = 'All' GROUP BY 1),
b AS (SELECT month, count(*) FILTER (WHERE kind = 'session') s, count(*) FILTER (WHERE kind = 'sent') e, count(*) FILTER (WHERE kind = 'join') w
      FROM fact_activity WHERE status_at_event = 'approved' AND month BETWEEN '2025-12' AND '2026-11' GROUP BY 1)
SELECT 'T02 report totals = sum of markets', CASE WHEN count(*) FILTER (WHERE m.s <> b.s OR m.e <> b.e OR m.w <> b.w) = 0 THEN 'PASS' ELSE 'FAIL' END,
       count(*) || ' months compared' FROM m JOIN b USING (month);

INSERT INTO test_results
WITH k AS (SELECT month, sum(edetail_sessions) s FROM out_kpi_market GROUP BY 1),
r AS (SELECT month, sessions s FROM out_report_monthly WHERE channel = 'e-detail' AND segment = 'All')
SELECT 'T03 e-detail sessions: KPI table = report cells',
       CASE WHEN (SELECT sum(s) FROM k) = (SELECT sum(s) FROM r) THEN 'PASS' ELSE 'FAIL' END, (SELECT sum(s) FROM k) || ' sessions';

-- small groups
INSERT INTO test_results SELECT 'T04 no published group of 1-4 HCPs',
  CASE WHEN (SELECT count(*) FROM out_report_monthly WHERE hcps_active BETWEEN 1 AND 4) = 0
        AND (SELECT count(*) FROM out_compliance WHERE hcps < 5) = 0
        AND (SELECT count(*) FROM out_simpson WHERE hcps < 5) = 0
        AND (SELECT count(*) FROM out_compliance_weekly WHERE hcps < 5) = 0
        AND (SELECT count(*) FROM out_ro_hour_profile WHERE hcps < 5) = 0 THEN 'PASS' ELSE 'FAIL' END,
  (SELECT count(*) FROM out_report_monthly WHERE suppressed) || ' cells suppressed (primary + secondary)';

-- the 8 planted events are found
INSERT INTO test_results SELECT 'T05 E1 outage: gap found then closed by backfill',
  CASE WHEN (SELECT sum(gap) FROM read_csv_auto('data/output/reconciliation_daily.csv') WHERE run_label = 'before_backfill') < 0
        AND (SELECT count(*) FROM read_csv_auto('data/output/reconciliation_daily.csv') WHERE run_label = 'after_backfill' AND gap <> 0) = 0
       THEN 'PASS' ELSE 'FAIL' END,
  (SELECT sum(gap) FROM read_csv_auto('data/output/reconciliation_daily.csv') WHERE run_label = 'before_backfill') || ' events before backfill, 0 after';
INSERT INTO test_results SELECT 'T06 E2 duplicates received and ignored',
  CASE WHEN sum(duplicates_ignored) > 0 THEN 'PASS' ELSE 'FAIL' END, sum(duplicates_ignored) || ' duplicate rows' FROM load_runs;
INSERT INTO test_results SELECT 'T07 E3 RO time zone found and fixed',
  CASE WHEN sum(naive_timestamps) > 0 AND sum(end_before_start_as_written) > 0 AND sum(end_before_start_after_fix) = 0 THEN 'PASS' ELSE 'FAIL' END,
  sum(end_before_start_as_written) || ' sessions ending before start as written, 0 after fix' FROM out_timezone_check;
INSERT INTO test_results
WITH s AS (SELECT * FROM out_simpson)
SELECT 'T08 E4 Simpson: DE lower overall, higher in every segment',
  CASE WHEN (SELECT ctr FROM s WHERE market = 'DE' AND segment = 'All') < (SELECT ctr FROM s WHERE market = 'PL' AND segment = 'All')
        AND (SELECT bool_and(d.ctr > p.ctr) FROM s d JOIN s p ON p.segment = d.segment AND p.market = 'PL' WHERE d.market = 'DE' AND d.segment <> 'All')
       THEN 'PASS' ELSE 'FAIL' END, 'overall DE ' || (SELECT ctr FROM s WHERE market = 'DE' AND segment = 'All') || ' vs PL ' || (SELECT ctr FROM s WHERE market = 'PL' AND segment = 'All');
INSERT INTO test_results SELECT 'T09 E5 idle sessions inflate naive engagement time',
  CASE WHEN naive_inflation BETWEEN 0.30 AND 0.45 THEN 'PASS' ELSE 'FAIL' END, '+' || round(100 * naive_inflation, 1) || '% naive vs capped'
FROM out_engagement_definition WHERE channel = 'e-detail';
INSERT INTO test_results SELECT 'T10 E6 current-status filter rewrites past months',
  CASE WHEN min(march_sessions_current_status_logic) < max(march_sessions_current_status_logic)
        AND max(march_sessions_point_in_time) = min(march_sessions_point_in_time) THEN 'PASS' ELSE 'FAIL' END,
  'March 2026: ' || max(march_sessions_current_status_logic) || ' -> ' || min(march_sessions_current_status_logic) || ' sessions (point-in-time stable)'
FROM out_point_in_time_restatement;
INSERT INTO test_results SELECT 'T11 E7 MLR expiry alert',
  CASE WHEN sum(sessions) > 0 THEN 'PASS' ELSE 'FAIL' END,
  sum(sessions) || ' sessions on ' || count(*) || ' contents, up to ' || max(max_days_after_expiry) || ' days late' FROM out_compliance;
INSERT INTO test_results SELECT 'T12 E8 August dip is seasonal (not escalated)',
  CASE WHEN abs(max(change_per_working_day) - min(change_per_working_day)) < 0.03 THEN 'PASS' ELSE 'FAIL' END,
  'per working day: ' || string_agg(year || ' ' || round(100 * change_per_working_day, 1) || '%', ', ') FROM out_august_check;
INSERT INTO test_results SELECT 'T13 ClinicalTrials.gov totalCount = rows received',
  CASE WHEN bool_and(complete) THEN 'PASS' ELSE 'FAIL' END, sum(received) || ' studies x market' FROM out_trials_by_market;

-- workbook (filled by src/check_workbook.py after Excel has recalculated the formulas)
INSERT INTO test_results
WITH s AS (SELECT 'reached' AS metric, market, hcps_reached::DOUBLE AS v FROM out_kpi_market WHERE month = '2026-10'
           UNION ALL SELECT 'edetail_sessions', market, edetail_sessions FROM out_kpi_market WHERE month = '2026-10'
           UNION ALL SELECT 'engaged_min', market, engaged_min_per_session FROM out_kpi_market WHERE month = '2026-10'
           UNION ALL SELECT 'ctr', market, ctr FROM out_kpi_market WHERE month = '2026-10'),
j AS (SELECT s.*, w.value FROM s JOIN workbook_kpi w USING (metric, market))
SELECT 'T14 Excel workbook KPIs = SQL (Oct 2026)',
  CASE WHEN (SELECT count(*) FROM workbook_kpi) = 0 THEN 'SKIP'
       WHEN count(*) = (SELECT count(*) FROM s) AND max(abs(value - v)) < 0.001 THEN 'PASS' ELSE 'FAIL' END,
  CASE WHEN (SELECT count(*) FROM workbook_kpi) = 0 THEN 'run src/check_workbook.py'
       ELSE count(*) || ' values, max difference ' || round(coalesce(max(abs(value - v)), 0), 6) END
FROM j;
