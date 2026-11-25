# How we compute engagement time

*Feature article for the users of the Client P monthly report (SIMULATED data, fictional client).*

"Average engagement time per e-detail session" is the figure brand teams quote most often. Until this month it was also the least reliable one. This article explains what changed, why, and how to read the new figure.

## What the old figure measured
Each e-detail session sends three kinds of events: `session_start` when the presentation opens, a `slide_view` each time a slide is shown, and `session_end` when it closes. The old report took the duration sent with `session_end` and averaged it.

That works when people close the presentation when they are done. It fails when they don't. A tab left open in the background keeps the session "alive" until the browser closes, sometimes hours later. Nobody is reading during that time, but the old figure counted every minute of it.

## What we changed
Engagement time now stops at the last sign of activity:

> engagement = from `session_start` to the earlier of `session_end` and the last `slide_view` + 30 seconds, minus any gap above 30 minutes between two slides.

The 30 seconds give credit for reading the last slide. The 30-minute rule handles a session paused in the middle and resumed later: the pause is not counted, the reading on both sides is.

A worked example. A session starts at 10:00:00, the last slide is shown at 10:02:00, and the tab is closed at 11:40:00. The old report counted 100 minutes. The new one counts 2.5 minutes.

## What it changes in the numbers
Over the year (December 2025 to November 2026), 617 of 35,097 e-detail sessions (1.8%) stayed idle for more than 30 minutes after their last slide. That small share was enough to inflate the average: **3.21 minutes per session with the old method, 2.32 minutes with the new one. The old figure was 38% too high.**

Two consequences matter more than the level itself:
- **Comparisons were unfair.** A market or a representative whose audience tends to leave tabs open looked more "engaging". The idle share, not reading time, drove the ranking.
- **Trends were noisy.** A browser update or a change in how HCPs work could move the old figure with no change in reading.

## How to read the new figure
- It is a **floor**: we only count time we can see. An HCP who reads one slide for five minutes without clicking is credited with 30 seconds after their last click. We prefer to under-count than to count idle tabs.
- Compare it **over time and between markets** with the same definition. Both the old and the new values are in the workbook (`KPI` sheet, columns G and H) for the transition period.
- It says nothing about the medicine or the message, only about how long the content was used.

## How it is built and checked
The rule is written once (`docs/kpi_definitions.md`) and implemented twice: in SQL (`sql/03_sessions.sql`) and as Excel formulas (`KPI` sheet). A test checks that both give the same value for every market (`sql/99_tests.sql`, T14). Another test checks that the idle sessions are found every month (T09).

## What's next
The source sends no session identifier, so sessions are rebuilt from the event order. Two sessions of the year overlapped and could not be split perfectly. We have asked the integration team for a `session_id`, which will remove that ambiguity.
