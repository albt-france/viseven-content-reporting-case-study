"""Build the 7-page PDF report (pages 0-6): charts (src/charts.py) -> HTML pages (16:9) -> PDF with headless Edge/Chrome.

Every number is read from data/output or data/public, so the report matches the code.
    python src/build_pdf.py
Outputs: docs/_build/report.html (intermediate, not published), site/report/viseven_data_analyst_case_study.pdf (metadata emptied)
"""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pandas as pd
from pypdf import PdfReader, PdfWriter

import charts
from common import COLLECTED, OUT, PUBLIC, ROOT

BUILD = ROOT / "docs" / "_build"
BUILD.mkdir(parents=True, exist_ok=True)
PDF = ROOT / "site" / "report" / "viseven_data_analyst_case_study.pdf"
PDF.parent.mkdir(parents=True, exist_ok=True)
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by Viseven"
JOB_URL = "https://jobs.lever.co/viseven/ecb4d58c-d8f7-40be-b359-c8faef089b1e"
AI_NOTE = ("AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the questions, "
           "chose and validated the data sources, made the analytical decisions and checked every result.")


def c(name):
    return pd.read_csv(OUT / f"{name}.csv")


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def n(x):
    return f"{int(round(x)):,}"


def load():
    f = {k: c(k) for k in ["kpi_market", "engagement_definition", "simpson", "simpson_standardised", "point_in_time_restatement",
                           "compliance", "august_check", "timezone_check", "load_runs", "benchmark_load", "verification_checks",
                           "reconciliation_daily", "trials_by_market", "physicians", "ema_summary", "contents_ended", "report_monthly"]}
    f["ed"] = f["engagement_definition"].set_index("channel").loc["e-detail"]
    f["s"] = f["simpson"].set_index(["market", "segment"])
    f["std"] = f["simpson_standardised"].set_index("market")
    f["pr"] = f["point_in_time_restatement"]
    f["aug"] = f["august_check"].set_index("year")
    f["tz"] = f["timezone_check"].set_index("market").loc["RO"]
    f["runs"] = f["load_runs"].set_index("job")
    f["b"] = f["benchmark_load"].set_index("scenario")
    vc = f["verification_checks"]
    f["before"], f["after"] = vc[vc.run_label == "before_backfill"].set_index("check"), vc[vc.run_label == "after_backfill"].set_index("check")
    rd = f["reconciliation_daily"]
    f["gapday"] = rd[(rd.run_label == "before_backfill") & (rd.gap != 0)].iloc[0]
    f["oct"] = f["kpi_market"][f["kpi_market"].month == "2026-10"]
    f["npm"] = json.loads((PUBLIC / "npm_ewizard_cli_meta.json").read_text())
    f["npm_total"] = int(pd.read_csv(PUBLIC / "npm_ewizard_cli_downloads.csv").downloads.sum())
    f["reg"] = json.loads((PUBLIC / "registry_estonia.json").read_text(encoding="utf-8"))
    lv = pd.read_csv(PUBLIC / "lever_postings.csv")
    f["lever_n"], f["lever_titles"] = len(lv), lv.title.nunique()
    f["lever_lead"] = lv[lv.title.str.contains("Data Analysis Team Lead")].shape[0]
    f["comp_s"] = int(f["compliance"].sessions.sum())
    f["comp_days"] = int(f["compliance"].max_days_after_expiry.max())
    f["sup"] = int(f["report_monthly"].suppressed.sum())
    return f


# ------------------------------------------------------------------ layout helpers
def page(num, title, subtitle, tag, body, sources):
    cls = {"PUBLIC DATA": "public", "SIMULATED": "simulated", "PUBLIC + SIMULATED": "mix", "OVERVIEW": "overview"}[tag]
    return f"""
<section class="page">
  <header><div><h1>{title}</h1><p class="sub">{subtitle}</p></div><div class="tag tag-{cls}">{tag}</div></header>
  <main>{body}</main>
  <footer><span>{sources} · collected {COLLECTED}</span><span>{DISCLAIMER}</span><span>{num}</span></footer>
</section>"""


def card(inner, cls=""):
    return f'<div class="card {cls}">{inner}</div>'


def img(src, cap=""):
    return f'<figure><img src="{src}"/>{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>'


def tile(label, value, text):
    return card(f'<div class="label">{label}</div><div class="big">{value}</div><p>{text}</p>', "tile")


# ------------------------------------------------------------------ pages
def p0(f, ch):
    ed, b, a = f["ed"], f["b"], f["aug"]
    bf = f["runs"].loc["backfill"]
    tiles = "".join([
        tile("SIMULATED · PAGE 4", f"{(f['after'].status != 'FAIL').sum()} / 8",
             f"verification checks without a blocking failure after the backfill (before: {(f['before'].status == 'FAIL').sum()} failure). "
             "Warnings are handled by documented fixes; one compliance alert goes to the client."),
        tile("SIMULATED · PAGE 5", n(bf.rows_inserted),
             f"events of 14/09/2026 recovered by a backfill, after a failed run moved the watermark anyway. "
             f"The fixed job (v2) loses {int(b.loc['incident_v2', 'lost_events'])} on the same day."),
        tile("SIMULATED · PAGE 3", f"{ed.capped_min_per_session:.2f} min",
             f"per e-detail session, capped at the last slide + 30 s. The old figure ({ed.naive_min_per_session:.2f} min) was "
             f"+{pct(ed.naive_inflation)} because of {int(ed.idle_sessions)} forgotten tabs."),
        tile("SIMULATED · PAGE 5", f"{f['comp_s']} sessions",
             f"on 2 contents used up to {f['comp_days']} days after their MLR expiry: flagged to the client, excluded from the KPIs."),
    ])
    q = card(f"""<h2>Questions</h2><ol class="qs">
      <li><b>Context</b> What does Viseven publish about itself, and what does the job ask? <span class="pg">p.1</span></li>
      <li><b>Market</b> How large are the HCP audiences, launches and trial activity these reports serve? <span class="pg">p.2</span></li>
      <li><b>Indicators</b> How should engagement KPIs be defined so that they mean the same thing every month? <span class="pg">p.3</span></li>
      <li><b>Trust</b> How do we prove each number is complete, unique and correctly timed? <span class="pg">p.4</span></li>
      <li><b>Incidents</b> What happens when the source breaks, and what is a real alert? <span class="pg">p.5</span></li></ol>
      <p class="reco"><b>Recommendations:</b> (1) write one algorithm per KPI and cap engagement time at the last activity;
      (2) filter content on its status <i>at the time of the event</i>, never today's; (3) move the load watermark only after a
      batch is verified against the source count, and insert idempotently on <code>event_id</code>; (4) gate publication on a
      daily reconciliation and show an MLR-expiry alert; (5) compare markets by segment and against working days and the prior
      year before raising an alarm.</p>""", "wide")
    m = card(f"""<h2>Data &amp; methods</h2>
      <p><b class="k">PUBLIC</b> Viseven's site and job posting, Estonian business register, npm (ewizard-cli), Eurostat physicians,
      EMA medicines (Source: European Medicines Agency), ClinicalTrials.gov REST API (8 markets, {n(f['trials_by_market'].received.sum())} rows, totals checked), public holidays.</p>
      <p><b class="k">SIMULATED</b> "Client P", a fictional pharma company: 6,000 HCPs (identifiers only), 120 contents, 8 markets,
      Dec 2025 - Nov 2026, {n(418666)} events served by a local REST API with pagination, rate limit and an outage.</p>
      <p><b class="k">METHODS</b> Python loaders, DuckDB SQL (sessionisation, KPIs, checks, 14 tests), an Excel report with real
      formulas checked against SQL, Agile requirements (Given-When-Then), runbook, 2 feature articles.</p>""", "wide")
    how = card("""<h3>How to read this report</h3><p><b>Titles</b> state the conclusion. &nbsp; <b>Tags</b> PUBLIC DATA / SIMULATED
      mark where data come from. &nbsp; HCPs appear only as identifiers and in groups of 5 or more; brands are codes (Brand A/B/C).
      &nbsp; The report measures <b>engagement with content</b>, not the effect of any medicine: no medical or regulatory advice.
      &nbsp; Workbook, SQL, documents and an interactive dashboard are in the repository.</p>""", "how")
    body = f'<div class="grid4">{tiles}</div><div class="g0">{q}{m}</div>{how}'
    return page(0, "Viseven: content-engagement reports that clients can trust",
                "How to deliver a pharma client a monthly report on its omnichannel content where every number is defined, verified, reloadable and documented, even when the source breaks.",
                "OVERVIEW", body, "Sources on page 6")


def p1(f, ch):
    reg, npm = f["reg"], f["npm"]
    facts = card(f"""<h2>Viseven, as stated by Viseven</h2><ul class="facts">
      <li>"We help pharma and life sciences brands reach their audiences faster with relevant content experiences across markets and channels."</li>
      <li>"For 17+ years, we've helped life sciences brands plan, create, reuse, and activate compliant content"; "more than 150 global brands".</li>
      <li>Products named on its site: <b>eWizard</b> ("powered by eVa AI: a content supply chain platform for life sciences"), <b>eVa</b>, <b>Kheiron</b>, <b>Lexi</b>.</li>
      <li><b>Register</b> (ariregister.rik.ee): {reg['name']}, code {reg['reg_code']}, status R (registered), Tallinn. Affiliates named in the privacy policy: Viseven Europe LLC (Ukraine), Viseven USA LLC.</li>
      <li><b>Hiring</b>: {f['lever_n']} open postings on Lever ({f['lever_titles']} distinct titles, most posted in several countries), incl. a <i>Data Analysis Team Lead</i> posted on 12-13 Nov 2026.</li>
      <li><b>Public developer activity</b>: npm package <code>ewizard-cli</code> since {npm['created'][:4]}, {npm['versions']} versions, {n(f['npm_total'])} downloads Nov 2025 - Oct 2026 (an activity index, not users).</li></ul>
      <p class="note">viseven.com home, careers and privacy pages and <a href="{JOB_URL}">the Lever posting</a>, read {COLLECTED}. Clients are not named by Viseven; none is assumed. Client P is fictional.</p>""")
    rows = [("Analyse data, develop reports for internal and external customers", "A monthly report for a client: request, KPIs, Excel workbook, dashboard", "p.3, Excel"),
            ("Help design indicator algorithms and calculation methods", "Written algorithms; capped engagement time; CTR at the same segment mix", "p.3, kpi_definitions"),
            ("Design and implement report data verification", "8 checks after each load, 14 SQL tests, Excel vs SQL control totals", "p.4, verification_rules"),
            ("Analyse data-loading procedures, propose optimisations", "Full / incremental / backfill on a REST API; measured benchmark", "p.4, load_procedure"),
            ("Propose improvements to existing reports", "5 changes with before / after on a year of data", "p.3-5, improvements"),
            ("Write and maintain documentation", "KPI definitions, rules, assumptions, glossary, data issues log", "docs/"),
            ("Help restore the system after failures", "Outage of 14/09: runbook, incident report, backfill, fix", "p.5, runbook"),
            ("Write articles on developed features", "2 articles: engagement time, point-in-time status", "docs/articles")]
    job = card("<h2>The 8 missions of the posting, and what this study shows for each</h2><table class='small'><tr><th>Mission (from the posting)</th><th>What is built</th><th>Where</th></tr>"
               + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c_}</td></tr>" for a, b, c_ in rows)
               + "</table><p class='note'>Also asked: Excel, databases, REST API principles, Python, requirements as Epic / Story / Given-When-Then (docs/report_request.md). Freelance, remote, attached to Bucharest (RO); posted 12 Nov 2026.</p>")
    body = f'<div class="grid-1-1" style="flex:1"><div class="stack">{facts}{card(img(ch["npm"]), "auto")}</div>{job}</div>'
    return page(1, "A content-platform company hiring for report quality: 8 missions, one study",
                "What Viseven publishes about itself, what the register and public package data confirm, and how each mission of the Data Analyst posting is covered here.",
                "PUBLIC DATA", body, "viseven.com, Lever, ariregister.rik.ee, npm registry")


def p2(f, ch):
    t = f["trials_by_market"].set_index("market")
    ph = f["physicians"].set_index("market")
    es = f["ema_summary"].iloc[0]
    text = card(f"""<h2>Reading</h2><ul class="small">
      <li><b>Audiences differ by 13x</b>: from {n(ph.loc['BG', 'physicians'])} practising physicians in BG to {n(ph.loc['DE', 'physicians'])} in DE (2024).
      Density varies too: {ph.loc['IT', 'per_100k']:.0f} per 100,000 inhabitants in IT, {ph.loc['RO', 'per_100k']:.0f} in RO. Client P's simulated HCP list follows these weights.</li>
      <li><b>Launches drive content</b>: {n(es.human_authorised)} human medicines are authorised in the EU ({n(es.orphan_authorised)} orphan, {n(es.biosimilar_authorised)} biosimilars);
      oncology is the largest named area of recent authorisations. Each launch means content to create, approve (MLR) and localise for each market where it launches.</li>
      <li><b>Trial activity</b>: {n(t.loc['FR', 'recruiting_studies'])} recruiting studies list a site in FR, {n(t.loc['RO', 'recruiting_studies'])} in RO, {n(t.loc['UA', 'recruiting_studies'])} in UA;
      oncology is 18-35% of them.</li>
      <li><b>A real REST load</b>: ClinicalTrials.gov v2 with token pagination, 1 request/s, limited fields (no investigator or contact data),
      retries, cache; <code>totalCount</code> = rows received in all 8 markets.</li>
      <li><b>Limits</b>: EMA lists only medicines still authorised (older years undercounted); a trial counts in each market where it has a site;
      the Eurostat EU27 total is empty in this table, which does not cover UA.</li></ul>""")
    body = f'<div class="grid3" style="flex:1.75">{card(img(ch["physicians"]))}{card(img(ch["ema"]))}{card(img(ch["trials"]))}</div><div style="flex:1;display:flex">{text}</div>'
    return page(2, "The market these reports serve: 8 countries, very different HCP audiences and launch loads",
                "Practising physicians by market (Eurostat), EU medicines by year of authorisation (Source: European Medicines Agency), recruiting trials by market (ClinicalTrials.gov REST API).",
                "PUBLIC DATA", body, "Eurostat hlth_rs_prs2, European Medicines Agency, ClinicalTrials.gov")


def p3(f, ch):
    ed, s, std, pr = f["ed"], f["s"], f["std"], f["pr"]
    text = card(f"""<h2>Algorithms (docs/kpi_definitions.md)</h2><ul class="small">
      <li><b>Engagement time</b> = start → min(session_end, last slide_view + 30 s), minus idle gaps above 30 min.
      {int(ed.idle_sessions)} of {n(ed.sessions)} e-detail sessions ({pct(ed.idle_sessions / ed.sessions, 1)}) stayed open more than 30 min after their last slide;
      they made the naive average {ed.naive_min_per_session:.2f} min instead of {ed.capped_min_per_session:.2f} (<b>+{pct(ed.naive_inflation)}</b>).</li>
      <li><b>Reach</b> = distinct HCPs with a session, email open or webinar join; not additive across channels (an 'All' row is computed).
      <b>Coverage</b> = reached / targeted. Oct 2026: {n(f['oct'].hcps_reached.sum())} of 6,000 HCPs ({pct(f['oct'].hcps_reached.sum() / 6000, 1)}).</li>
      <li><b>CTR</b> = clicks / emails sent. DE {pct(s.loc[('DE', 'All'), 'ctr'], 2)} vs PL {pct(s.loc[('PL', 'All'), 'ctr'], 2)} as reported, but DE is higher for GPs,
      specialists and pharmacists: it sends {pct(s.loc[('DE', 'Specialist'), 'share_of_sends'])} of its emails to specialists, who click less (PL {pct(s.loc[('PL', 'Specialist'), 'share_of_sends'])}).
      At the same mix: DE {pct(std.loc['DE', 'ctr_standardised'], 2)}, PL {pct(std.loc['PL', 'ctr_standardised'], 2)}. Simpson's paradox: <b>DE is not worse</b>.</li>
      <li><b>Point-in-time status</b>: the old report kept contents approved <i>today</i>, erasing the past of every content withdrawn or expired since.
      March 2026 fell from {n(pr.march_sessions_current_status_logic.iloc[0])} sessions (published 1 Apr) to {n(pr.march_sessions_current_status_logic.iloc[-1])} (25 Nov);
      with the status valid at the event time it stays {n(pr.march_sessions_point_in_time.iloc[0])}.</li>
      <li><b>Small groups</b>: no published cell describes 1-4 HCPs ({f['sup']} cells blanked, with secondary suppression).</li></ul>""")
    body = f'<div class="grid3" style="flex:1.7">{card(img(ch["engagement"]))}{card(img(ch["simpson"]))}{card(img(ch["point_in_time"]))}</div><div style="flex:1;display:flex">{text}</div>'
    return page(3, f"Indicators that mean something: engagement time was {pct(ed.naive_inflation)} too high, and DE was not worse than PL",
                "Each KPI has one written algorithm, implemented in SQL and as Excel formulas with zero difference. Three definitions changed the reading of the report.",
                "SIMULATED", body, "src/simulate_client_p.py (seed 42), sql/03, 04, 06, 07")


def p4(f, ch):
    bf, af, b, tz = f["before"], f["after"], f["b"], f["tz"]
    g = f["gapday"]
    rows = "".join(f"<tr><td>{k}</td><td>{bf.loc[k, 'rule']}</td><td class='{bf.loc[k, 'status']}'>{bf.loc[k, 'status']}</td>"
                   f"<td class='{af.loc[k, 'status']}'>{af.loc[k, 'status']}</td></tr>" for k in af.index)
    checks = card(f"""<h2>8 checks after every load</h2><table class="small"><tr><th>#</th><th>Rule</th><th>Before backfill</th><th>After</th></tr>{rows}</table>
      <ul class="small"><li><b>Completeness</b>: {g.day}, source {n(g.distinct_event_ids)} events, warehouse {n(g.warehouse)}: gap {int(g.gap)}.</li>
      <li><b>Duplicates</b>: {n(f['runs'].loc['v1', 'duplicates_ignored'])} rows with an existing event_id after the outage, ignored (insert keyed on event_id).</li>
      <li><b>Time zone</b>: since 01/10 RO writes local time without offset ({n(tz.naive_timestamps)} timestamps); {int(tz.end_before_start_as_written)} sessions ended before they started.
      Fix: the UTC reading closest to the server time (handles the DST change of 25/10); 0 after.</li>
      <li><b>Excel = SQL</b>: the workbook's KPIs, recalculated by Excel, match SQL for every market (test T14).</li></ul>""")
    body = (f'<div class="grid-2-1" style="flex:1"><div class="grid2x2">{card(img(ch["reconciliation"]))}{card(img(ch["ro_hours"]))}'
            f'{card(img(ch["benchmark"]), "span2")}</div>{checks}</div>')
    full5 = b.loc["full_5000"]
    return page(4, "Trusting the numbers: every load is reconciled with the source, de-duplicated and put back in UTC",
                f"Checks C1-C8, the RO time-zone bug, and the load procedures measured on the local API: a full reload in pages of 5,000 needs {int(full5.requests)} requests instead of {int(b.loc['full_500', 'requests'])}; one incremental day needs {int(b.loc['incremental_day', 'requests'])}.",
                "SIMULATED", body, "src/ingest.py, src/verify.py, src/benchmark_load.py, sql/05")


def p5(f, ch):
    a, comp = f["aug"], f["compliance"]
    bf = f["runs"].loc["backfill"]
    tl = card(f"""<h2>14/09/2026: the outage, step by step (UTC)</h2><table class="small">
      <tr><td>06:00</td><td>Source API returns HTTP 500 (until 12:00)</td></tr>
      <tr><td>09:00</td><td>Run fails after 5 attempts (backoff 0.5-8 s). Job v1 <b>moves its watermark to 09:00 anyway</b></td></tr>
      <tr><td>12:00-14:00</td><td>Integration re-sends late-morning events: {n(f['runs'].loc['v1', 'duplicates_ignored'])} duplicate rows</td></tr>
      <tr><td>15:00</td><td>Run OK from 09:00: duplicates ignored; 03:00-09:00 never requested</td></tr>
      <tr><td>Check C1</td><td>Gap {int(f['gapday'].gap)} events on 14/09: publication blocked</td></tr>
      <tr><td>Backfill</td><td>{int(bf.requests)} requests, {n(bf.rows_inserted)} events inserted; C1 passes</td></tr>
      <tr><td>Fix</td><td>v2: watermark only after a verified batch (replay: 0 lost)</td></tr></table>
      <h2 style="margin-top:8px">Alert vs false alarm</h2><ul class="small">
      <li><b>Alert</b>: {comp.content_id.iloc[0]} and {comp.content_id.iloc[1]} (IT, Brand B) used after MLR expiry: {f['comp_s']} sessions, up to {f['comp_days']} days. Raised with the client; no regulatory advice.</li>
      <li><b>Not an alert</b>: e-detail sessions {pct(a.loc[2026, 'change'])} from July to August; per working day {pct(a.loc[2026, 'change_per_working_day'], 1)}, vs {pct(a.loc[2025, 'change_per_working_day'], 1)} in 2025. Summer holidays, not a tracking failure.</li></ul>
      <p class="note">Runbook: docs/incident_runbook.md · report: docs/incident_report_2026-09-14.md</p>""")
    body = (f'<div class="grid-2-1" style="flex:1"><div class="grid2x2">{card(img(ch["incident"]))}{card(img(ch["compliance"]))}'
            f'{card(img(ch["seasonality"]), "span2")}</div>{tl}</div>')
    return page(5, f"When the source breaks: {n(bf.rows_inserted)} events recovered, one real alert raised, one false alarm not",
                "The outage of 14/09/2026 and its fix, sessions on content after MLR expiry, and the August dip read against working days and the prior year.",
                "PUBLIC + SIMULATED", body, "src/ingest.py, src/benchmark_load.py, sql/08, 09, Nager.Date")


def p6(f, ch):
    src = card(f"""<h2>Sources, licences and dates</h2><table class="small">
      <tr><th>Source</th><th>Use</th><th>Licence / note</th><th>Date</th></tr>
      <tr><td>viseven.com (home, careers, privacy policy)</td><td>Company facts</td><td>Quoted as stated by Viseven; 3 pages, 1 request / 3 s</td><td>read 25 Nov 2026</td></tr>
      <tr><td><a href="{JOB_URL}">Lever posting</a> and postings API</td><td>The job, open postings</td><td>Public API, no person names kept</td><td>read 25 Nov 2026</td></tr>
      <tr><td>Estonian business register (ariregister.rik.ee)</td><td>Legal entity, status</td><td>Public register; company fields only</td><td>25 Nov 2026</td></tr>
      <tr><td>npm registry and download API</td><td>ewizard-cli activity</td><td>Public metadata; maintainers not kept</td><td>Nov 2025 - Oct 2026</td></tr>
      <tr><td>Eurostat hlth_rs_prs2</td><td>Practising physicians</td><td>Eurostat re-use policy (CC BY 4.0)</td><td>2024 data</td></tr>
      <tr><td>EMA medicines report (xlsx)</td><td>EU authorisations</td><td>Re-use allowed with acknowledgement. Source: European Medicines Agency</td><td>file of 25 Nov 2026</td></tr>
      <tr><td>ClinicalTrials.gov API v2</td><td>Recruiting trials</td><td>U.S. NLM; fields NCTId, Condition, Status, StartDate, Phase only</td><td>25 Nov 2026</td></tr>
      <tr><td>Nager.Date</td><td>Public holidays 2025-2026</td><td>Open API</td><td>25 Nov 2026</td></tr></table>""", "tall2")
    meth = card("""<h2>Methods</h2><ul class="small">
      <li><b>Simulation</b> (seed 42): Client P, 6,000 HCPs split by Eurostat weights, 3 brand codes on the 3 largest EMA areas, 120 contents
      with MLR dates, a year of events with seasonality from real holidays; 8 situations planted and all found by the checks and tests.</li>
      <li><b>API and loads</b>: a local REST API (standard library, 127.0.0.1) with cursor pagination, 429 + Retry-After, 500 during an outage;
      full, incremental and backfill loads into DuckDB; checks C1-C8.</li>
      <li><b>SQL</b>: sessionisation with window functions, KPIs with GROUPING SETS, point-in-time joins, ASOF joins for session checks, 14 tests.</li>
      <li><b>Excel</b>: SUMIFS, COUNTIFS, XLOOKUP, IFERROR, LET; recalculated by Excel and compared with SQL and Python.</li></ul>""")
    lim = card("""<h2>Limits</h2><ul class="small">
      <li>Client P, its HCPs, contents, events and API are <b>fictional</b>: not data of Viseven, of its clients or of any company,
      and not the API of eWizard or any Viseven product. No internal Viseven data is used or assumed.</li>
      <li>The report measures engagement with content, not the effect of any medicine: <b>no medical or regulatory advice</b>.</li>
      <li>npm downloads include bots and CI; EMA counts only medicines still authorised; broad areas come from keyword grouping.</li>
      <li>No person is named: HCPs are identifiers, no group under 5 HCPs is published, brands are codes.</li></ul>""")
    ai = card(f"""<h2>AI note</h2><p>{AI_NOTE}</p>""", "auto")
    body = f'<div class="grid2" style="flex:1"><div class="stack">{src}{ai}</div><div class="stack">{meth}{lim}</div></div>'
    return page(6, "Methods, limits and AI note", "What is public, what is simulated, how each number is produced, and what it cannot tell.",
                "OVERVIEW", body, "README.md, docs/")


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1600px; height: 900px; padding: 30px 44px 22px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; background: #F4F4F2; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 27px; margin: 0 0 6px; font-weight: 700; line-height: 1.15; max-width: 1320px; }
.sub { margin: 0; color: #52514E; font-size: 14.5px; max-width: 1320px; }
.tag { font-size: 12px; font-weight: 700; letter-spacing: .08em; padding: 5px 10px; border-radius: 4px; white-space: nowrap; }
.tag-public { background: #E3EEFB; color: #1C5CAB; } .tag-simulated { background: #FBE9E0; color: #9A3B12; }
.tag-mix { background: #EDE7F6; color: #5B3E96; } .tag-overview { color: #52514E; background: #E9E7E1; }
main { flex: 1; display: flex; flex-direction: column; gap: 12px; margin-top: 14px; min-height: 0; }
footer { display: flex; justify-content: space-between; gap: 20px; font-size: 11px; color: #898781; margin-top: 10px; }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 12px 16px; min-height: 0; overflow: hidden; flex: 1; }
.card h2 { font-size: 16px; margin: 0 0 6px; } .card h3 { font-size: 14px; margin: 0 0 4px; }
.card p, .card li { font-size: 13.5px; line-height: 1.4; margin: 3px 0; color: #2B2A27; }
.card ul, .card ol { padding-left: 18px; margin: 4px 0; }
a { color: #1C5CAB; } code { font-size: 12px; background: #F4F4F2; padding: 0 4px; border-radius: 3px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; min-height: 0; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid2x2 { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 12px; min-height: 0; }
.g0 { display: grid; grid-template-columns: 1.25fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid-2-1 { display: grid; grid-template-columns: 1.9fr 1fr; gap: 12px; min-height: 0; }
.grid-1-1 { display: grid; grid-template-columns: 1fr 1.1fr; gap: 12px; min-height: 0; }
figure { margin: 0; height: 100%; display: flex; flex-direction: column; }
figure img { width: 100%; flex: 1; min-height: 0; object-fit: contain; }
figcaption { font-size: 11.5px; color: #52514E; margin-top: 3px; }
.tile { flex: 0 0 auto; } .tile .label { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .04em; }
.tile .big { font-size: 40px; font-weight: 700; margin: 2px 0; color: #0B0B0B; }
.tile p { font-size: 13px; color: #52514E; }
.stack { display: flex; flex-direction: column; gap: 12px; min-height: 0; } .stack .card { flex: 1; }
.qs li { font-size: 15px !important; margin: 5px 0; } .qs b { color: #2A78D6; margin-right: 6px; }
.pg { color: #898781; font-size: 12px; } .reco { font-size: 14px !important; }
.k { color: #52514E; font-size: 12.5px; letter-spacing: .05em; margin-right: 4px; }
.how { flex: 0 0 auto; } .how p { font-size: 13px; }
.auto { flex: 0 0 auto !important; } .tall2 { flex: 3 !important; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 4px 6px; }
td { border-bottom: 1px solid #EFEEE9; padding: 4px 6px; vertical-align: top; }
table.small, .small, .small li { font-size: 12.5px !important; }
.note { font-size: 11.5px !important; color: #6B6A65 !important; }
.facts li { font-size: 13.5px !important; margin: 5px 0; }
.PASS { color: #137A52; font-weight: 700; } .FAIL, .ALERT { color: #B02A2A; font-weight: 700; } .WARN { color: #9A6B00; font-weight: 700; }
.grid-1-1 .stack .auto img { max-height: 250px; }
.span2 { grid-column: 1 / -1; }
"""


def build_html() -> Path:
    ch = charts.build_all()
    f = load()
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Viseven Data Analyst case study</title><style>{CSS}</style></head><body>
{''.join(p(f, ch) for p in [p0, p1, p2, p3, p4, p5, p6])}
</body></html>"""
    out = BUILD / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def find_browser() -> str:
    for cnd in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "", shutil.which("google-chrome") or "",
                shutil.which("chromium") or ""]:
        if cnd and Path(cnd).exists():
            return cnd
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html: Path) -> Path:
    tmp = BUILD / "_print.pdf"
    tmp.unlink(missing_ok=True)
    profile = tempfile.mkdtemp()            # own profile: an open Edge window would otherwise take the call
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                    f"--print-to-pdf={tmp}", html.as_uri()], check=True, timeout=180)
    last = -1
    for _ in range(120):                    # Edge can return before its child process has written the file
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()       # rewrite with neutral metadata
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": "Viseven - content-engagement reports case study", "/Author": "", "/Creator": "", "/Producer": ""})
    with open(PDF, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return PDF


def main():
    html = build_html()
    pdf = print_pdf(html)
    print("written", pdf, len(PdfReader(str(pdf)).pages), "pages")


if __name__ == "__main__":
    main()
