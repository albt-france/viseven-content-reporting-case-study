# Why the report now uses point-in-time content status

*Feature article for the users of the Client P monthly report (SIMULATED data, fictional client).*

If you compared the March 2026 figures of the report in April and again in November, you saw two different numbers. Nobody changed March. The report did. This article explains why, and what we changed so that a past month stays the same.

## The old rule
Every content used with HCPs has an MLR approval with a start and an expiry date, and can be withdrawn early. The report should only count activity on approved material. The old report did this with one filter: **keep the contents whose status is "approved" today.**

That filter answers the wrong question. It asks "is this content approved now?" instead of "was this content approved when the HCP used it?".

## What went wrong
When a content expires or is withdrawn, its status changes today. With the old filter, all of its past activity disappears from every month, retroactively. The report then shows fewer sessions in months that were already published, and the drop is bigger the more contents have ended since.

Over the year, 30 contents ended (20 expired, 10 withdrawn). Here is March 2026, as the old logic would have published it at different dates:

| Published on | March 2026 sessions, old logic | Point-in-time |
|---|---|---|
| 1 April 2026 | 3,746 | 3,775 |
| 1 July 2026 | 3,156 | 3,775 |
| 1 October 2026 | 3,043 | 3,775 |
| 25 November 2026 | 2,360 | 3,775 |

Refreshed today, the old report would show 37% fewer sessions for March than really happened on approved content. A brand team comparing March with October would see growth that is partly an artefact.

## The new rule
The report now keeps the **status valid at the time of each event**. Each content has a status history (approved from / to, then expired or withdrawn from). Each session is matched to the status line whose period contains the session's start time:

> `valid_from <= session start < valid_to` and status = approved.

A session on a content approved at the time counts, even if that content was withdrawn later. March stays at 3,775 sessions whenever the report is refreshed (test T10 in `sql/99_tests.sql`).

## What happens to activity on expired content
The new rule also shows the opposite case: activity on a content **after** its approval ended. Those sessions are no longer silently mixed in or silently dropped. They are excluded from the KPIs and listed in the `Compliance` sheet so the client can act. This year: 412 sessions on two contents in Italy (Brand B), up to 19 days after their MLR expiry. The report states the facts; the decision belongs to the client's compliance team.

## The general lesson
Any filter on an attribute that changes over time (status, owner, territory, price) must use the value **at the time of the event**. Using today's value leaks the present into the past.

## Where to find it
- Rule: `docs/kpi_definitions.md` (common rules).
- SQL: `sql/07_point_in_time_status.sql`.
- Workbook: the KPIs count approved activity only; the `Compliance` sheet lists the rest.
