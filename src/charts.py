"""Matplotlib charts for the PDF report (docs/img/*.png). Every number is read from data/output or data/public.

Style: light grey-beige page, white cards, Segoe UI; a tag on each chart (PUBLIC DATA / SIMULATED / PUBLIC + SIMULATED);
red for alerts, dashed lines for thresholds. EMA charts carry "Source: European Medicines Agency".
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from common import MARKETS, OUT, PUBLIC, ROOT

IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
BLUE, LIGHT, GREY, RED, INK, MUTED, GRID, ORANGE, GREEN = ("#2A78D6", "#C9DDF5", "#A3A19A", "#D03B3B", "#0B0B0B", "#52514E",
                                                           "#E1E0D9", "#EB6834", "#1BAF7A")
AREA_C = {"Oncology": "#2A78D6", "Cardiovascular & metabolic": "#EB6834", "Immunology & inflammation": "#1BAF7A",
          "Neurology & psychiatry": "#B04FC2", "Infectious diseases": "#EDA100", "Rare & genetic": "#7FB3EA", "Other": "#C8C6BF"}
TAG_C = {"PUBLIC DATA": ("#E3EEFB", "#1C5CAB"), "SIMULATED": ("#FBE9E0", "#9A3B12"), "PUBLIC + SIMULATED": ("#EDE7F6", "#5B3E96")}
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#EFEEE9", "grid.linewidth": 0.8, "axes.axisbelow": True})


def csv(name):
    return pd.read_csv(OUT / f"{name}.csv")


def fig(title, tag, w=5.2, h=3.4):
    f, ax = plt.subplots(figsize=(w, h))
    f.text(0.015, 0.975, title, fontsize=10.5, fontweight="bold", color=INK, va="top")
    bg, fg = TAG_C[tag]
    f.text(0.985, 0.975, tag, fontsize=7, fontweight="bold", color=fg, va="top", ha="right",
           bbox=dict(boxstyle="round,pad=0.3", fc=bg, ec="none"))
    return f, ax


def save(f, name, note=None, top=0.84):
    if note:
        f.text(0.015, 0.015, note, fontsize=7, color=MUTED)
    f.tight_layout(rect=(0, 0.04 if note else 0, 1, top))
    p = IMG / f"{name}.png"
    f.savefig(p, dpi=200, facecolor="white")
    plt.close(f)
    return p.as_uri()


def physicians():
    d = csv("physicians").sort_values("physicians")
    f, ax = fig("Practising physicians by market, 2024", "PUBLIC DATA")
    ax.barh(d.market, d.physicians / 1000, color=BLUE)
    for y, (v, p) in enumerate(zip(d.physicians, d.per_100k)):
        ax.text(v / 1000 + 4, y, f"{v / 1000:,.0f}k · {p:.0f} per 100k", va="center", fontsize=7.5, color=MUTED)
    ax.set_xlim(0, d.physicians.max() / 1000 * 1.55)
    ax.set_xlabel("thousand practising physicians")
    ax.grid(axis="y", visible=False)
    return save(f, "physicians", "Source: Eurostat hlth_rs_prs2 (2024). UA not covered.")


def ema():
    d = csv("ema_by_year_area")
    d = d[d.year >= 2016]
    p = d.pivot_table(index="year", columns="area_group", values="medicines", fill_value=0)
    order = [a for a in AREA_C if a in p.columns]
    f, ax = fig("EU human medicines still authorised, by year of authorisation", "PUBLIC DATA")
    bottom = 0
    for a in order:
        ax.bar(p.index.astype(int), p[a], bottom=bottom, color=AREA_C[a], label=a, width=0.75)
        bottom = bottom + p[a]
    ax.legend(fontsize=6.5, ncol=2, frameon=False, loc="upper left")
    ax.set_ylabel("medicines")
    ax.grid(axis="x", visible=False)
    ax.set_xticks(p.index.astype(int))
    ax.tick_params(axis="x", labelsize=7)
    return save(f, "ema", "Source: European Medicines Agency. Only medicines still authorised (survivor bias); 2026 to 25 Nov.")


def trials():
    d = csv("trials_by_market").sort_values("recruiting_studies")
    f, ax = fig("Recruiting clinical trials with a site in the market", "PUBLIC DATA")
    ax.barh(d.market, d.recruiting_studies, color=LIGHT, label="all areas")
    ax.barh(d.market, d.oncology, color=BLUE, label="oncology")
    for y, (v, o) in enumerate(zip(d.recruiting_studies, d.oncology_pct)):
        ax.text(v + 60, y, f"{v:,} · {o:.0f}% onc.", va="center", fontsize=7.5, color=MUTED)
    ax.set_xlim(0, d.recruiting_studies.max() * 1.35)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    return save(f, "trials", "ClinicalTrials.gov API v2, 8 paginated loads, totalCount = rows received in every market (25 Nov 2026).")


def npm():
    d = pd.read_csv(PUBLIC / "npm_ewizard_cli_downloads.csv", parse_dates=["day"])
    m = d.set_index("day").downloads.resample("MS").sum()
    f, ax = fig("Public npm downloads of ewizard-cli, by month", "PUBLIC DATA", 5.2, 3.0)
    ax.bar(m.index, m.values, width=20, color=BLUE)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%y"))
    ax.tick_params(axis="x", labelsize=7)
    ax.grid(axis="x", visible=False)
    return save(f, "npm", f"{int(d.downloads.sum()):,} downloads Nov 2025 - Oct 2026; include bots and CI: an activity index, not users.")


def engagement():
    d = csv("engagement_monthly")
    f, ax = fig("Minutes per e-detail session: naive vs capped", "SIMULATED")
    ax.plot(d.month, d.naive_min, color=RED, marker="o", ms=3, label="naive (session_end duration)")
    ax.plot(d.month, d.capped_min, color=BLUE, marker="o", ms=3, label="capped (last slide + 30 s)")
    ax.fill_between(d.month, d.capped_min, d.naive_min, color=RED, alpha=0.08)
    ax.set_ylim(0, d.naive_min.max() * 1.25)
    ax.legend(fontsize=7, frameon=False, loc="lower left")
    ax.tick_params(axis="x", labelsize=6.5, rotation=45)
    e = csv("engagement_definition").set_index("channel").loc["e-detail"]
    return save(f, "engagement", f"Year: {e.naive_min_per_session:.2f} vs {e.capped_min_per_session:.2f} min, naive +{100 * e.naive_inflation:.0f}% from {int(e.idle_sessions)} idle sessions.")


def simpson():
    d = csv("simpson")
    segs = ["GP", "Specialist", "Pharmacist", "All"]
    f, ax = fig("Email click-through rate, DE vs PL, by HCP segment", "SIMULATED")
    x = range(len(segs))
    for i, (mk, c) in enumerate([("DE", BLUE), ("PL", ORANGE)]):
        v = [d[(d.market == mk) & (d.segment == s)].ctr.iloc[0] for s in segs]
        bars = ax.bar([j + (i - 0.5) * 0.38 for j in x], v, width=0.36, color=c, label=mk)
        for b, val in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, val + 0.001, f"{val * 100:.1f}%", ha="center", fontsize=7, color=MUTED)
    ax.set_xticks(list(x))
    ax.set_xticklabels(["GP", "Specialist", "Pharmacist", "All (as reported)"])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=7, frameon=False)
    ax.grid(axis="x", visible=False)
    sh = d[d.segment == "Specialist"].set_index("market").share_of_sends
    return save(f, "simpson", f"DE higher in every segment, lower overall: specialists get {sh['DE']:.0%} of DE sends vs {sh['PL']:.0%} in PL.")


def point_in_time():
    d = csv("point_in_time_restatement")
    f, ax = fig("March 2026 sessions, as published on each date", "SIMULATED")
    lbl = pd.to_datetime(d.published_on).dt.strftime("%d %b")
    ax.bar(lbl, d.march_sessions_current_status_logic, color=[LIGHT, LIGHT, LIGHT, RED], width=0.6, label="old: current status")
    ax.axhline(d.march_sessions_point_in_time.iloc[0], color=BLUE, lw=1.6, ls="--", label="point-in-time status (stable)")
    for i, v in enumerate(d.march_sessions_current_status_logic):
        ax.text(i, v + 50, f"{v:,}", ha="center", fontsize=7.5, color=MUTED)
    ax.set_ylim(0, d.march_sessions_point_in_time.max() * 1.25)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("date the report is refreshed")
    return save(f, "point_in_time", "A current-status filter erases the past of every content withdrawn or expired since.")


def reconciliation():
    d = csv("reconciliation_daily")
    d = d[(d.day >= "2026-09-10") & (d.day <= "2026-09-18")]
    f, ax = fig("Daily reconciliation against the source count", "SIMULATED")
    b = d[d.run_label == "before_backfill"]
    a = d[d.run_label == "after_backfill"]
    days = pd.to_datetime(b.day).dt.strftime("%d/%m")
    ax.bar(days, b.distinct_event_ids, color=LIGHT, label="source /count")
    ax.bar(days, b.warehouse, color=[RED if g else BLUE for g in b.gap], width=0.45, label="warehouse before backfill")
    ax.scatter(days, a.warehouse.values, color=GREEN, zorder=3, s=18, label="after backfill")
    for x, g, v in zip(days, b.gap, b.warehouse):
        if g:
            ax.text(x, v + 40, f"{int(g)}", ha="center", color=RED, fontsize=8, fontweight="bold")
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=1)
    ax.set_ylim(0, b.distinct_event_ids.max() * 1.45)
    ax.grid(axis="x", visible=False)
    return save(f, "reconciliation", "Check C1: distinct events per day of updated_at; the gap blocks publication until backfilled.")


def ro_hours():
    d = csv("ro_hour_profile")
    f, ax = fig("RO session starts by hour (UTC)", "SIMULATED")
    for v, c, ls in [("Sep 2026", GREY, "-"), ("Oct-Nov as written", RED, "-"), ("Oct-Nov fixed", BLUE, "--")]:
        x = d[d.version == v].set_index("hour_utc").sessions.reindex(range(24), fill_value=0)
        ax.plot(x.index, x / x.sum(), color=c, ls=ls, lw=1.6, label=v)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("hour of session_start, UTC")
    ax.legend(fontsize=7, frameon=False)
    t = csv("timezone_check").set_index("market").loc["RO"]
    return save(f, "ro_hours", f"Local time without offset: {int(t.end_before_start_as_written)} sessions ended before they started; 0 after the fix.")


def benchmark():
    d = csv("benchmark_load").set_index("scenario")
    s = ["full_500", "full_5000", "incremental_day"]
    lbl = ["full reload\n500 / page", "full reload\n5,000 / page", "incremental\n1 day (4 runs)"]
    f, ax = fig("Load procedures, measured against the local API", "SIMULATED")
    bars = ax.bar(lbl, d.loc[s, "requests"], color=[GREY, BLUE, GREEN], width=0.55)
    for b, r, sec, rows in zip(bars, d.loc[s, "requests"], d.loc[s, "seconds"], d.loc[s, "rows_loaded"]):
        ax.text(b.get_x() + b.get_width() / 2, r * 1.15, f"{int(r):,} req · {sec:.0f} s\n{int(rows):,} rows", ha="center", fontsize=7, color=MUTED)
    ax.set_yscale("log")
    ax.set_ylim(1, d.loc[s, "requests"].max() * 8)
    ax.set_ylabel("HTTP requests (log scale)")
    ax.grid(axis="x", visible=False)
    return save(f, "benchmark", "Rate limit 5 req/s, client throttled to 4.5 req/s: time follows the number of requests.")


def incident():
    d = csv("benchmark_load").set_index("scenario")
    f, ax = fig("Same day replayed: job v1 vs job v2", "SIMULATED", 5.2, 3.0)
    lbl = ["v1: watermark moves\nafter a failed run", "v2: watermark moves\nafter a verified batch"]
    v = [d.loc["incident_v1", "lost_events"], d.loc["incident_v2", "lost_events"]]
    bars = ax.bar(lbl, v, color=[RED, GREEN], width=0.5)
    for b, val in zip(bars, v):
        ax.text(b.get_x() + b.get_width() / 2, val + 15, f"{int(val)} events lost", ha="center", fontsize=8, color=INK)
    ax.set_ylim(0, max(v) * 1.3 + 10)
    ax.grid(axis="x", visible=False)
    return save(f, "incident", "14/09/2026 03:00 -> 15/09 03:00; source down 06:00-12:00 UTC (HTTP 500).")


def compliance():
    d = csv("compliance_weekly")
    c = csv("compliance")
    f, ax = fig("Sessions per week on content after its MLR expiry (IT, Brand B)", "SIMULATED")
    weeks = sorted(d.week.unique())
    for i, (cid, col) in enumerate(zip(c.content_id, [RED, ORANGE])):
        x = d[d.content_id == cid].set_index("week").sessions.reindex(weeks, fill_value=0)
        exp = c[c.content_id == cid].mlr_expiry.iloc[0]
        ax.bar([j + (i - 0.5) * 0.38 for j in range(len(weeks))], x.values, width=0.36, color=col, label=f"{cid} (expired {exp})")
    ax.set_xticks(range(len(weeks)))
    ax.set_xticklabels([pd.Timestamp(w).strftime("week of %d/%m") for w in weeks], fontsize=7)
    ax.legend(fontsize=7, frameon=False)
    ax.set_ylabel("sessions")
    ax.grid(axis="x", visible=False)
    return save(f, "compliance", f"{int(c.sessions.sum())} sessions, up to {int(c.max_days_after_expiry.max())} days after expiry; weeks with >= 5 HCPs shown. Alert, excluded from KPIs.")


def seasonality():
    d = csv("seasonality")
    f, ax = fig("E-detail sessions per market working day", "PUBLIC + SIMULATED")
    for src, c in [("prior-year report", GREY), ("event data", BLUE)]:
        x = d[d.source == src]
        ax.plot(pd.to_datetime(x.month), x.sessions_per_market_working_day, color=c, marker="o", ms=3, label=src)
    for m in ["2025-08", "2026-08"]:
        ax.axvspan(pd.Timestamp(m) - pd.Timedelta(days=12), pd.Timestamp(m) + pd.Timedelta(days=12), color="#FFF4C2", zorder=0)
    a = csv("august_check").set_index("year")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%y"))
    ax.tick_params(axis="x", labelsize=6.5)
    ax.set_ylim(0, d.sessions_per_market_working_day.max() * 1.3)
    ax.legend(fontsize=7, frameon=False, loc="lower left")
    return save(f, "seasonality", f"August per working day: {a.loc[2026, 'change_per_working_day']:.1%} in 2026 vs {a.loc[2025, 'change_per_working_day']:.1%} in 2025 (raw {a.loc[2026, 'change']:.0%}). Holidays: Nager.Date.")


def build_all():
    return {f.__name__: f() for f in [physicians, ema, trials, npm, engagement, simpson, point_in_time, reconciliation,
                                      ro_hours, benchmark, incident, compliance, seasonality]}


if __name__ == "__main__":
    print(list(build_all()))
