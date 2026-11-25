# Proposals to improve the existing report

*SIMULATED data (fictional Client P). Each proposal: the problem, the change, the effect measured on the year Dec 2025 - Nov 2026.*

## 1. Cap engagement time at the last activity
- **Problem**: the report used the duration sent with `session_end`. Tabs left open for hours inflated it.
- **Change**: engagement ends at min(session_end, last slide_view + 30 s); idle gaps above 30 min between slides are cut (`docs/kpi_definitions.md`).
- **Before / after**: 3.21 min vs **2.32 min** per e-detail session; the naive figure was **+38%**, from 617 sessions (1.8%) left idle for more than 30 minutes.
- **Why it matters**: the naive figure moved with how many tabs were forgotten, not with how long HCPs read.

## 2. Use the content status at the event time
- **Problem**: the report kept contents whose status is "approved" **today**. Every expiry or withdrawal silently erased that content's past activity, so past months changed each time the report was refreshed.
- **Change**: point-in-time join (`sql/07_point_in_time_status.sql`).
- **Before / after**: March 2026 = 3,775 sessions with the point-in-time status, stable. With the old logic the same month showed 3,746 sessions if published on 1 April, 3,156 on 1 July, 3,043 on 1 October and **2,360 on 25 November (-37%)**. 30 contents ended during the year (20 expired, 10 withdrawn).

## 3. Add an MLR-expiry alert
- **Problem**: nothing showed when field teams kept using material after its MLR expiry.
- **Change**: check C7 and a Compliance sheet; those sessions are excluded from KPIs and listed for the client.
- **Found**: 2 IT Brand B e-detail contents, **412 sessions** after expiry (230 and 182), by 199 and 160 HCPs, up to **19 days** after expiry.
- **Note**: the report flags the facts; what to do is the client's compliance decision (no regulatory advice).

## 4. Compare markets by segment
- **Problem**: the raw click-through rate ranked DE (4.00%) below PL (5.34%).
- **Change**: CTR by HCP segment and at the same segment mix next to the raw CTR (`sql/06_simpson_ctr.sql`, Excel `Segments`).
- **Before / after**: DE is higher in every segment (GP 7.25% vs 6.24%, specialists 3.04% vs 2.70%, pharmacists 5.97% vs 5.05%); at the same mix DE 4.97% vs PL 4.31%. DE simply sends 75% of its emails to specialists, who click less, vs 20% in PL.

## 5. Read seasonal dips against working days and the prior year
- **Problem**: a -31% month (August) looks like a tracking failure.
- **Change**: sessions per market working day (public holidays, Nager.Date) and the prior-year report next to the month (`sql/09_seasonality.sql`).
- **Before / after**: -31.0% Jul -> Aug 2026 raw; -24.8% per working day, vs -26.2% in 2025: the usual summer pattern. No incident raised.

## 6. Make the load safe to re-run
- Watermark only after a verified batch; insert keyed on `event_id`; daily reconciliation against the source count as a publication gate (`docs/load_procedure.md`, `docs/incident_report_2026-09-14.md`).

## 7. Next ideas (not built)
- Show each KPI with its "data complete up to" time, from C4.
- Add a "reach by HCP segment" view per brand when each cell has at least 5 HCPs.
- Store the published monthly figures (a snapshot per publication) so any restatement is visible and explained.
