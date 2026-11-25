# KPI definitions and algorithms

*SIMULATED data (fictional Client P). Grain of the report: month x market, with breakdowns by channel and HCP segment. SQL: `sql/03_sessions.sql`, `sql/04_kpi.sql`. Excel: `KPI` sheet.*

## Common rules
| Rule | Definition |
|---|---|
| Time | All timestamps converted to UTC (`sql/01_load.sql`); month = month of the event in UTC. November 2026 is partial (to 24 Nov). |
| Eligible activity | Only events on a content whose status **at the event time** is `approved` (point-in-time join on `content_status`, `valid_from <= ts < valid_to`). Activity on expired or withdrawn content goes to the Compliance list, not to the KPIs. |
| Uniqueness | One row per `event_id` (duplicates ignored at load). |
| Small groups | A published cell must describe 0 or at least 5 HCPs. Cells with 1-4 active HCPs are blanked, plus the smallest other segment of the same month x market x channel (secondary suppression). |
| Segments | HCP specialty from the master data: `GP`, `Specialist`, `Pharmacist`. |

## Sessionisation (e-detail and web)
1. Take the events of one HCP on one content, ordered by UTC time (`session_start` before `slide_view` before `session_end` on ties).
2. A new session starts at each `session_start` (running count of `session_start` = session number).
3. For each session: `start_ts` = session_start, `end_ts` = session_end, `last_slide_ts` = last slide_view, `slides` = number of slide views.

Known limit: when the same HCP opens the same content twice and the second session starts before the first one closes, the end is attached to the later session (2 sessions in the year, see `data_issues_log.md`).

## Indicators

### HCPs targeted
Count of HCPs in Client P's target list for the market (and segment). Constant over the year. *Oct 2026: 6,000 in total, DE 1,538.*

### HCPs reached
`count(DISTINCT hcp_id)` with at least one e-detail or web session, email open or webinar join in the month. Not additive across channels (use the `All` channel row); additive across markets (an HCP belongs to one market).
*Oct 2026: 3,130 HCPs reached.*

### Coverage
`HCPs reached / HCPs targeted`. *Oct 2026: 3,130 / 6,000 = 52.2%.*

### Frequency
`(sessions + email opens + webinar joins) / HCPs reached`, same month and market. *Oct 2026, DE: 2.12 interactions per reached HCP.*

### E-detail sessions
Number of sessions of the `e-detail` channel (sessionised as above). *Oct 2026: 3,298.*

### Engagement time per e-detail session (capped) — replaces the naive duration
```
capped_s = (min(session_end, last_slide_view + 30 s) - session_start)
           - sum over consecutive slide views of max(gap - 30 min, 0)
engagement_min_per_session = sum(capped_s) / sessions / 60
```
- **Why**: a tab left open sends its `session_end` when the browser is closed, hours later. The naive duration (reported by `session_end`) counted that idle time.
- **Worked example**: start 10:00:00, slides at 10:00:02, 10:00:31, 10:01:05, last slide 10:02:00, session_end 11:40:00. Naive = 100 min. Capped = 10:02:30 - 10:00:00 = 2.5 min.
- **Effect on the year**: 617 of 35,097 e-detail sessions (1.8%) were idle for more than 30 minutes after the last slide; they inflated the naive average from 2.32 to 3.21 min per session (**+38%**).

### Open rate and click-through rate (CTR)
`open rate = email_open / email_sent`; `CTR = email_click / email_sent` (per sent email, not per open). Events are counted in their own month.
**Read by segment**: markets send to different HCP mixes. Compare markets with the CTR by segment or the CTR at the same segment mix (`sql/06_simpson_ctr.sql`, Excel `Segments`):
```
CTR_standardised(market) = sum over segments of CTR(market, segment) x share of the segment in all sends
```
*Dec 2025 - Nov 2026: DE 4.00% vs PL 5.34% raw; DE 4.97% vs PL 4.31% at the same mix.*

### Webinar joins
Number of `webinar_join` events.

### Compliance: sessions after MLR expiry
Sessions whose `start_ts` is on or after the content's MLR expiry or withdrawal date. Reported with sessions, HCPs (>= 5), first and last use, and days after expiry. *2 contents, 412 sessions, up to 19 days after expiry.*

## Change log
| Date | Change | Why |
|---|---|---|
| 2026-11-25 | Engagement time capped at the last slide view + 30 s | idle tabs inflated the naive duration by 38% |
| 2026-11-25 | Point-in-time content status | the current-status filter rewrote past months |
| 2026-11-25 | CTR shown by segment and at the same mix | raw CTR ranked DE below PL although DE is higher in every segment |
