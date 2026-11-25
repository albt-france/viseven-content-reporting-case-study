# Verification rules

*SIMULATED data. Run after every load: `python src/verify.py --label <name>`. Results: `data/output/verification_checks.csv`, workbook sheet `Verification`. The same checks are re-derived in SQL in `sql/05_verification.sql`; assertions in `sql/99_tests.sql`.*

Status: **PASS**; **FAIL** blocks publication; **WARN** handled by a documented transformation; **ALERT** reported to the client.

| ID | Rule | Threshold | On failure | Result before backfill | After backfill |
|---|---|---|---|---|---|
| C1 | Distinct events per day of `updated_at` in the warehouse = source `/v1/events/count?group_by=day` | 0 days with a gap | FAIL: find the window in `load_runs`, backfill it (`ingest.py --backfill`), re-run the checks | FAIL: 1 day, -715 events (2026-09-14) | PASS |
| C2 | `event_id` unique in the warehouse; duplicates received are counted | 0 duplicates stored | FAIL: stop the load, check the insert key | PASS: 0 stored, 3,214 received and ignored | PASS |
| C3 | Required fields present, `event_type` and `channel` in the allowed lists, timestamps parseable, durations >= 0 | 0 rows | FAIL: quarantine the rows, ask the source owner | PASS | PASS |
| C4 | Last `updated_at` loaded within 6 h of the run clock | <= 360 min | FAIL: check the scheduler and the API status | PASS | PASS |
| C5 | Every timestamp carries an offset (`Z`) | 0 rows | WARN: read naive RO timestamps as Europe/Bucharest (`sql/01_load.sql`); ask the integration team for a fix | WARN: RO, 2,062 rows from 2026-10-01 | WARN (handled) |
| C6 | No session ends before it starts (timestamps as written) | 0 sessions | WARN: same root cause as C5; must be 0 after the fix | WARN: RO, 304 sessions | WARN; 0 after fix |
| C7 | No session on a content after its MLR expiry or withdrawal | 0 sessions | ALERT: list in the Compliance sheet, exclude from KPIs, raise with the client (no regulatory advice) | ALERT: 412 sessions, 2 contents (IT, Brand B), up to 19 days | ALERT |
| C8 | `hcp_id` and `content_id` exist in the master data | 0 rows | FAIL: hold the rows, refresh the master data | PASS | PASS |

## Report-level checks (`sql/99_tests.sql`)
| Test | Rule |
|---|---|
| T01 | `event_id` unique after de-duplication |
| T02 | Report totals = sum of markets = activity base, every month |
| T03 | E-detail sessions identical in the KPI table and the report cells |
| T04 | No published group of 1-4 HCPs (report, compliance list, segment table) |
| T05-T12 | The 8 data situations of the year are found (outage gap, duplicates, time zone, Simpson, idle sessions, current-status leak, MLR expiry, seasonal dip) |
| T13 | ClinicalTrials.gov: `totalCount` = rows received, every market |
| T14 | Excel KPIs (after recalculation) = SQL, October 2026, max difference < 0.001 |

## Why counting by `updated_at`
`updated_at` is the source's receive time (UTC, set by the server). It is the replication key of the incremental load, so a day of `updated_at` is exactly what one set of runs must have loaded. Counting by `event_ts` would mix load completeness with time-zone problems (C5).
