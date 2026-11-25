# Report request: Client P monthly content-engagement report

*SIMULATED. Client P is a fictional pharma company active in 8 European markets (RO, PL, FR, DE, ES, IT, BG, UA). The request below is written the way an internal or external customer request would be turned into requirements.*

## Epic

**EPIC-01 · A monthly engagement report Client P can trust.**
As Client P's commercial-excellence team, we want one monthly report of how healthcare professionals (HCPs) engage with our approved omnichannel content (remote e-detailing, approved emails, webinars, landing pages), so that we can steer content and field activity by market, with every number defined, verified, reloadable and documented.

Out of scope: any claim about a medicine, its efficacy or its safety; any regulatory or medical advice. The report measures **engagement with content**, not treatment outcomes.

## Stories and acceptance criteria

### STORY-01 · Defined indicators
As a brand manager, I want each KPI to have one written algorithm, so that two analysts get the same number.

```gherkin
Scenario: engagement time ignores forgotten tabs
  Given an e-detail session whose last slide_view is at 10:02:00 and whose session_end is at 11:40:00
  When the report computes engagement time
  Then the session counts from session_start to 10:02:30 (last slide_view + 30 s)
  And the naive duration (98 min) is not used

Scenario: reach is not double counted across channels
  Given HCP00042 opened an approved email and attended a webinar in October 2026
  When the report counts HCPs reached for October 2026
  Then HCP00042 is counted once in the "All channels" row
```

### STORY-02 · Complete and verified data
As the report owner, I want the data checked against the source before publication, so that a missing hour never reaches the client.

```gherkin
Scenario: a gap is caught before publication
  Given the source /v1/events/count reports 1,801 events received on 2026-09-14
  And the warehouse holds 1,086 events for that day
  When the verification runs
  Then check C1 fails with a gap of 715 events on 2026-09-14
  And the report is not published until the window is backfilled and C1 passes

Scenario: duplicates do not inflate the KPIs
  Given the source sends the same event_id twice
  When the loader inserts the batch
  Then the event is stored once and the duplicate is counted in load_runs.duplicates_ignored
```

### STORY-03 · Point-in-time content status
As a brand manager, I want past months to stay the same after a content is withdrawn, so that I can compare months.

```gherkin
Scenario: a withdrawn content keeps its past activity
  Given content CNT0xx was MLR-approved from 2026-01-10 to 2026-05-31 and withdrawn on 2026-05-31
  And it had sessions in March 2026
  When the March 2026 figures are recomputed in November 2026
  Then the March sessions on CNT0xx are still counted
  Because the filter uses the status valid at the event time, not today's status
```

### STORY-04 · Compliance alert
As the client's compliance contact, I want to see any use of material after its MLR expiry, so that we can act quickly.

```gherkin
Scenario: expired content still in use
  Given content CNT006 (IT, Brand B) has an MLR expiry date of 2026-10-21
  And sessions start on CNT006 after 2026-10-21
  When the monthly report is produced
  Then the Compliance sheet lists CNT006 with the number of sessions, HCPs (>= 5) and days after expiry, marked ALERT
  And those sessions are not counted in the engagement KPIs
```

### STORY-05 · Readable comparisons, no false alarms
As a regional director, I want market comparisons that are fair and alerts that are real.

```gherkin
Scenario: compare click-through at the same segment mix
  Given DE sends 75% of its emails to specialists and PL 20%
  When the report ranks DE and PL on click-through rate
  Then it shows the CTR by segment and the CTR at the same segment mix next to the raw CTR

Scenario: a seasonal dip is not reported as a tracking failure
  Given e-detail sessions fall by 31% from July to August 2026
  And the prior-year report shows a fall of 34% from July to August 2025
  And the fall per working day is similar in both years (-25% vs -26%)
  When the analyst reviews the month
  Then no tracking incident is raised and the report notes the seasonal pattern
```

## Definition of done
- KPIs computed in SQL (`sql/04_kpi.sql`) and as Excel formulas (`excel/client_p_monthly_report.xlsx`), with zero difference (`sql/99_tests.sql`, T14).
- Verification checks C1-C8 run after every load (`src/verify.py`), results in the workbook's Verification sheet.
- No published cell describes fewer than 5 HCPs.
- Documentation updated: `docs/kpi_definitions.md`, `docs/verification_rules.md`, `docs/load_procedure.md`.
