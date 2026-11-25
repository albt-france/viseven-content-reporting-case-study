# Incident report: source outage of 14/09/2026 and 715 missing events

*SIMULATED incident on the fictional Client P pipeline, replayed with `src/ingest.py --incremental --job v1`. All times UTC.*

## Summary
On Monday 14/09/2026 the source API returned HTTP 500 from 06:00 to 12:00. The incremental job (v1, as found) ran at 09:00, failed after 5 attempts, and **still moved its watermark to 09:00**. The next run (15:00) started from 09:00, so the events received by the source between 03:00 and 09:00 were never loaded: **715 events** (39.7% of the day). The daily reconciliation (check C1) found the gap; a backfill of the window restored all 715 events; the checks passed after the backfill. When the source recovered, the integration re-sent late-morning events several times: **3,214 duplicate rows**, ignored by the insert keyed on `event_id`.

## Timeline
| Time | Event |
|---|---|
| 14/09 03:00 | Run OK, watermark 03:00 |
| 14/09 06:00 | Source API starts returning 500 |
| 14/09 09:00 | Run fails: 5 attempts, 5 x HTTP 500 (backoff 0.5 to 8 s). **Watermark moved to 09:00 anyway** (v1 behaviour) |
| 14/09 12:00 | Source API back |
| 14/09 12:00-14:00 | Integration re-sends events of 09:00-12:00 several times (3,214 duplicate rows) |
| 14/09 15:00 | Run OK from 09:00: 3,214 duplicates ignored. Events of 03:00-09:00 not requested |
| Verification | C1 FAIL: 2026-09-14, source 1,801 distinct events, warehouse 1,086, gap -715 |
| Recovery | `ingest.py --backfill --since 2026-09-14T03:00:00Z --until 2026-09-14T09:00:00Z`: 3 requests, 715 received, 715 inserted, 0 already present |
| After | C1 PASS (0 days with a gap); SQL and workbook rebuilt |

## Impact
- Data: 715 events missing for 14/09 until the backfill, all markets.
- Report: none published with the gap (C1 blocks publication).
- Duplicates: 0 stored (3,214 received, all ignored).

## Root cause
The v1 job set `watermark = as_of` at the end of every run, whether the run succeeded or not. A failed run therefore skipped its window.

## Fix (v2)
- The watermark moves only after a **verified batch**: all pages received and rows received = `/v1/events/count` for the window.
- On failure the watermark stays; the next run reloads the same window with the new data.
- Replayed on the same day (`src/benchmark_load.py`, scenarios `incident_v1` / `incident_v2`): v1 loses 715 events, v2 loses none.

## Prevention
- Alert on any failed run and on C1 / C4 before the report is built.
- Keep the daily reconciliation against the source count as a publication gate.
- Ask the integration owner to make retries idempotent on their side too (they caused the duplicates).
