# Glossary

| Term | Meaning in this study |
|---|---|
| **HCP** | Healthcare professional (physician, pharmacist...). Shown only as an identifier (`HCP00001`) and in counts of 5 or more. |
| **MLR** | Medical, Legal, Regulatory review: the approval a promotional or medical content needs before use. An approval has an expiry date. |
| **E-detailing** | Remote or digital presentation of product information to an HCP, slide by slide, often led by a representative. |
| **CLM** | Closed-loop marketing: interactive presentations whose usage data (slides, time) go back to the marketing team. |
| **Approved email** | An email template approved through MLR that a representative or the brand team sends to HCPs. |
| **Omnichannel** | Coordinating several channels (field, remote, email, web, webinars) around the same HCP. |
| **Session** | The events of one HCP on one content from `session_start` to `session_end`. |
| **Engagement time (capped)** | Time from session start to the last activity + 30 s (see `kpi_definitions.md`). |
| **Reach / coverage** | Distinct HCPs with at least one interaction / share of the target list. |
| **CTR** | Click-through rate: email clicks / emails sent. |
| **REST API** | An HTTP interface: resources at endpoints (`/v1/events`), methods (`GET`), status codes (200 OK, 400 bad request, 401 unauthorised, 429 too many requests, 500 server error). |
| **Pagination** | Getting a large result page by page: by cursor (`next_cursor`) or token (`nextPageToken`). |
| **Retry-After** | Header sent with 429: how many seconds to wait before retrying. |
| **Exponential backoff** | Waiting 0.5, 1, 2, 4, 8 s between retries. |
| **Full load / incremental load** | Reloading everything / loading only what changed since the last run. |
| **Watermark** | The last `updated_at` successfully loaded; the next incremental run starts from it. |
| **Idempotent** | Running the same load twice gives the same result (insert keyed on `event_id`). |
| **Backfill** | Reloading a past window that was missed. |
| **Point-in-time status** | The status a content had at the time of the event, not today's. |
| **Simpson's paradox** | A trend in every group that reverses when the groups are pooled, because the groups have different sizes. |
| **Working day** | Monday to Friday, not a national public holiday of the market. |
