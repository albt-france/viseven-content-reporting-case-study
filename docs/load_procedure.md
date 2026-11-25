# Load procedure: full, incremental, backfill

*SIMULATED source: the local REST API of the fictional Client P platform (`src/mock_api.py`, 127.0.0.1 only; not the API of eWizard or of any Viseven product). The same rules are applied to a real public API in `src/collect_trials.py` (ClinicalTrials.gov).*

## The source API
| Item | Value |
|---|---|
| Endpoint | `GET /v1/events?updated_since=&updated_until=&as_of=&cursor=&limit=` (limit 500 by default, 5,000 max) |
| Order | `updated_at` (server receive time, UTC), then `event_id`; `updated_since` exclusive, `updated_until` inclusive |
| Pagination | opaque cursor (`next_cursor`, `null` on the last page) |
| Control | `GET /v1/events/count?from=&to=[&group_by=day]`: rows and distinct `event_id`s |
| Auth | `Authorization: Bearer <token>` (dummy token written to `.env` at start) |
| Errors | 400 bad parameter, 401 bad token, 429 + `Retry-After` above 5 requests/s, 500 when the source is down |

## Full load (`python src/ingest.py --full`)
Empties `raw_events`, loads every event with `updated_at <= 2026-09-01 00:00 UTC` in pages of 5,000, checks rows received = `/count`, sets the watermark. Used once, or to rebuild after a schema change.

## Incremental load (`python src/ingest.py --incremental [--job v1|v2]`)
Runs every 6 hours (03:00, 09:00, 15:00, 21:00 UTC). Each run asks for `(watermark, run time]`, pages of 500.
- **v2 (current)**: after the last page, compare rows received with `/count` for the same window. Equal = verified: insert (one transaction) and move the watermark to the run time. Otherwise, or on error, keep the watermark: the next run reloads the window.
- **v1 (as found)**: moved the watermark to the run time even when the run failed. This caused the 14/09/2026 incident (`incident_report_2026-09-14.md`). Kept in the code only to replay the incident.

## Backfill (`python src/ingest.py --backfill --since <ISO> --until <ISO>`)
Reloads one window at today's clock. Safe to repeat: rows already present are ignored.

## Rules shared by every mode
- **Rate**: at most 4.5 requests/s (one request every 0.22 s), below the 5/s limit.
- **Retries**: 5 attempts; exponential backoff 0.5, 1, 2, 4, 8 s on 5xx and network errors; on 429 wait `Retry-After` seconds.
- **Idempotent insert** keyed on `event_id` (`INSERT OR IGNORE`, after removing duplicates inside the batch). Duplicates are counted, never stored twice.
- **Logging**: every run goes to `load_runs` (window, requests, 429, 5xx, rows received / inserted, duplicates ignored, source count, status, watermark after, seconds).
- **Checks after each load**: `python src/verify.py` (C1-C8, `verification_rules.md`).

## Benchmark (`python src/benchmark_load.py`, measured on one laptop, 25 Nov 2026)
| Scenario | Requests | Seconds | Rows loaded | Rows / request | Events lost |
|---|---|---|---|---|---|
| Full reload, whole year, 500 rows / page | 854 | 204.1 | 418,666 | 490 | 0 |
| Full reload, whole year, 5,000 rows / page | 102 | 37.9 | 418,666 | 4,105 | 0 |
| Incremental, one day (4 runs), 500 / page | 11 | 3.1 | 1,697 | 154 | 0 |
| 14/09 replayed with job v1 | 19 | 13.1 | 1,088 | 57 | **715** |
| 14/09 replayed with job v2 | 24 | 15.5 | 1,803 | 75 | 0 |

Request counts include the `/count` controls and the retries (HTTP 429 and 500). With a rate limit, **time follows the number of requests**, not the number of rows.

## Optimisation proposals
1. **Large pages for full reloads**: 5,000 rows per page instead of 500 cuts requests by 8x (854 to 102) and time by 5x (204 s to 38 s). Keep 500 for incremental runs, where a window rarely holds more than one page.
2. **Incremental instead of full**: one day costs 11 requests and 3 s, against 854 requests and 204 s for a full reload. Reserve full reloads for rebuilds.
3. **Verify before moving the watermark** (v2): costs one `/count` request per run (5 more requests on the incident day) and removes silent data loss (715 events on 14/09 with v1).
4. **Count by day in one call** (`group_by=day`): the daily reconciliation of a whole year is one request instead of 360.
5. **Ask the source for a `session_id`** and for idempotent retries on their side: removes the session-rebuild ambiguity and the duplicates at the root.
6. Not done here, for a larger volume: load pages into a staging table and merge once per run; parallel windows within the rate limit.

## Real REST load: ClinicalTrials.gov (`src/collect_trials.py`)
Same discipline on a real API: token pagination (`nextPageToken`), 1 request per second, limited `fields`, retries with backoff and `Retry-After`, a raw cache per market (resume after an error), and a completeness check `totalCount` = rows received = distinct `NCTId`. Result on 25 Nov 2026: 8 markets, 18,414 study x market rows, complete in every market (RO 411, PL 1,390, FR 6,074, DE 2,890, ES 3,121, IT 4,096, BG 285, UA 147).
