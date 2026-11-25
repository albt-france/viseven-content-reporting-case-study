# Incident runbook: source down, data missing or late

*For the Client P reporting pipeline (SIMULATED). Use it before reading the incident report of 14/09/2026: try to find the cause from the symptoms.*

## 1. Detect
Signals, in the order they usually appear:
- `load_runs.status` starts with `failed` (HTTP 5xx after 5 attempts), or `http_5xx` > 0 on a run.
- Check **C1** fails: a day where the warehouse holds fewer distinct events than the source `/v1/events/count`.
- Check **C4** fails: the last `updated_at` loaded is more than 6 hours old.
- A KPI drops on one day only, for all markets at once (a tracking or load problem usually hits every market; a real behaviour change rarely does).

## 2. Contain
1. **Do not publish** the report while C1 or C4 fails. Tell the report's users the expected delay.
2. Check the API: `GET /health`, then one small `GET /v1/events?limit=1`. 500 = source side; 401 = token; 429 = rate limit (respect `Retry-After`).
3. Note the time the problem started and the last good run (`load_runs`, `watermark_after`).

## 3. Diagnose
```sql
-- failed or suspicious runs
SELECT run_id, job, as_of, updated_since, status, watermark_after FROM load_runs
WHERE status LIKE 'failed%' OR http_5xx > 0 ORDER BY run_id;
-- days with a gap (after verify.py)
SELECT day, distinct_event_ids, warehouse, gap FROM read_csv_auto('data/output/reconciliation_daily.csv')
WHERE gap <> 0;
```
Questions to answer:
- Did the watermark move **after** a failed run? If yes, the window `(updated_since, as_of]` of that run is missing.
- Is the gap one window or several? Does it match a failed run exactly?
- Did the source re-send events after recovery (duplicates)? `duplicates_ignored` in the next runs.

## 4. Recover
1. Backfill the missing window (idempotent: events already present are ignored):
   `python src/ingest.py --backfill --since <updated_since of the failed run> --until <as_of of the failed run>`
2. Re-run the checks: `python src/verify.py --label after_backfill`. C1 must pass.
3. Re-run SQL and the workbook: `python src/run_sql.py`, `python src/build_workbook.py`, `python src/check_workbook.py`.
4. Publish, with a note on the delay if the report was late.

## 5. Prevent
- The watermark moves **only after a verified batch** (rows received = source count for the window). A failed run keeps the watermark; the next run reloads the window (job v2, `ingest.py --job v2`).
- Insert keyed on `event_id`, so retries and backfills can be run safely.
- Alert on any failed run and on C1 / C4, before the report is built.
- Write the incident report within 2 working days: timeline, impact, recovery, prevention.

## 6. Communicate
- To the client: what was affected (dates, markets, metrics), what was done, whether published figures changed. No blame, facts only.
- Internally: the incident report and the change to the procedure.
