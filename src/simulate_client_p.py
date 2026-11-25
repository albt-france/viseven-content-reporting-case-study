"""Simulate the content-engagement source system of the fictional "Client P" (SIMULATED, seed 42).

Client P is a fictional pharma company active in 8 markets. Nothing here is data of Viseven, of its clients or of any
real company. HCPs are identifiers only (HCP00001...), brands are codes (Brand A/B/C), contents are CNT001...

Calibration on public data (see docs/assumptions.md):
- HCPs per market follow the weight of practising physicians (Eurostat hlth_rs_prs2, latest year), ~6,000 in total;
  UA is not in Eurostat: assumed the size of RO.
- Brand therapeutic areas = the 3 largest named areas of EMA human authorisations 2023-2026 (Source: European
  Medicines Agency); content counts follow their weights.
- Working days use the real public holidays (Nager.Date) of each market.

Outputs (data/sim/, not published, regenerated in seconds):
  hcps.csv, contents.csv, content_status_history.csv, markets.csv, prior_year_monthly.csv,
  events.parquet = the SOURCE table served by src/mock_api.py (with updated_at, duplicates and the RO time-zone bug).
Hidden truth of the 8 planted events: data/_hidden_truth.csv (never published).
    python src/simulate_client_p.py
"""
import numpy as np
import pandas as pd

from common import MARKETS, PUBLIC, ROOT, SIM, area

rng = np.random.default_rng(42)
START, END = pd.Timestamp("2025-12-01"), pd.Timestamp("2026-11-24")      # inclusive; as_of = 2026-11-25 00:00 UTC
TZ = {"RO": "Europe/Bucharest", "PL": "Europe/Warsaw", "FR": "Europe/Paris", "DE": "Europe/Berlin",
      "ES": "Europe/Madrid", "IT": "Europe/Rome", "BG": "Europe/Sofia", "UA": "Europe/Kiev"}
LANG = {"RO": "ro", "PL": "pl", "FR": "fr", "DE": "de", "ES": "es", "IT": "it", "BG": "bg", "UA": "uk"}
N_HCP = 6000
SPEC_MIX = {"DE": (0.20, 0.70, 0.10), "PL": (0.60, 0.25, 0.15)}            # GP, Specialist, Pharmacist
DEFAULT_MIX = (0.40, 0.45, 0.15)
SPECS = ["GP", "Specialist", "Pharmacist"]
# email targeting mix (share of sends) and click-through per send by segment: planted Simpson effect DE vs PL
SEND_MIX = {"DE": (0.18, 0.75, 0.07), "PL": (0.65, 0.20, 0.15)}
CTR_SEG = {"GP": 0.060, "Specialist": 0.026, "Pharmacist": 0.045}
CTR_MULT = {"DE": 1.15, "PL": 1.00, "RO": 0.95, "FR": 1.05, "ES": 1.00, "IT": 0.97, "BG": 0.92, "UA": 0.90}
P_OPEN = {"GP": 0.31, "Specialist": 0.28, "Pharmacist": 0.30}
SEASON = {1: .95, 2: 1.0, 3: 1.05, 4: 1.0, 5: .98, 6: 1.0, 7: .95, 8: .70, 9: 1.05, 10: 1.08, 11: 1.05, 12: .88}
TRUTH = []


def truth(n, name, detail, value):
    TRUTH.append({"event": n, "name": name, "detail": detail, "value": value})


# ------------------------------------------------------------------ reference data
def holidays():
    h = pd.read_csv(PUBLIC / "holidays.csv", parse_dates=["date"])
    return {m: set(h[h.market == m].date) for m in MARKETS}


def markets_table():
    e = pd.read_csv(PUBLIC / "eurostat_physicians.csv").set_index("market")
    phys = {m: float(e.loc[m, "physicians"]) if m in e.index else float(e.loc["RO", "physicians"]) for m in MARKETS}
    tot = sum(phys.values())
    raw = {m: N_HCP * phys[m] / tot for m in MARKETS}
    n = {m: int(round(v)) for m, v in raw.items()}
    n["DE"] += N_HCP - sum(n.values())
    d = pd.DataFrame({"market": MARKETS, "physicians_eurostat": [phys[m] for m in MARKETS],
                      "physicians_source": ["Eurostat" if m != "UA" else "assumed = RO" for m in MARKETS],
                      "target_hcps": [n[m] for m in MARKETS], "tz": [TZ[m] for m in MARKETS], "language": [LANG[m] for m in MARKETS]})
    return d


def hcps_table(mk):
    rows, rep_no = [], 0
    reps = {}
    for r in mk.itertuples():
        k = max(2, int(round(r.target_hcps / 160)))
        reps[r.market] = [f"REP{rep_no + i + 1:02d}" for i in range(k)]
        rep_no += k
        mix = SPEC_MIX.get(r.market, DEFAULT_MIX)
        spec = rng.choice(SPECS, size=r.target_hcps, p=mix)
        for s in spec:
            rows.append({"market": r.market, "specialty": s, "rep_id": rng.choice(reps[r.market]),
                         "propensity": rng.gamma(1.2, 1.0)})
    h = pd.DataFrame(rows)
    h.insert(0, "hcp_id", [f"HCP{i + 1:05d}" for i in range(len(h))])
    return h, reps


def brands():
    d = pd.read_csv(PUBLIC / "ema_medicines.csv", parse_dates=["authorisation_date"])
    h = d[(d.category == "Human") & (d.status == "Authorised") & (d.authorisation_date.dt.year >= 2023)]
    top = h.area_group[h.area_group != "Other"].value_counts().head(3)
    return pd.DataFrame({"brand": ["Brand A", "Brand B", "Brand C"], "therapeutic_area": top.index,
                         "ema_authorisations_2023_2026": top.values, "weight": (top / top.sum()).values})


def contents_table(br):
    """120 contents: 45 e-detail, 40 approved-email, 10 webinar, 25 landing-page, spread over the 8 markets."""
    types = ["e-detail"] * 45 + ["approved-email"] * 40 + ["webinar"] * 10 + ["landing-page"] * 25
    rows = []
    for i, t in enumerate(types):
        m = MARKETS[i % 8]
        rows.append({"content_id": f"CNT{i + 1:03d}", "type": t, "market": m, "language": LANG[m],
                     "brand": rng.choice(br.brand, p=br.weight)})
    c = pd.DataFrame(rows)
    c["channel"] = c.type.map({"e-detail": "e-detail", "approved-email": "approved-email", "webinar": "webinar", "landing-page": "web"})
    # MLR approval and expiry. Per market and type, the first two contents are "evergreen" (approved before the period,
    # valid after it) so each market always has live material; the others start or end during the year.
    appr, exp, wd = [], [], []
    for (m, t), g in c.groupby(["market", "type"], sort=False):
        for j, _ in enumerate(g.index):
            if j < 2:
                a = pd.Timestamp("2025-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
                e = a + pd.DateOffset(months=24)
                w = pd.NaT
            else:
                a = pd.Timestamp("2025-02-01") + pd.Timedelta(days=int(rng.integers(0, 560)))
                e = a + pd.DateOffset(months=int(rng.choice([12, 18])))
                w = a + pd.Timedelta(days=int(rng.integers(60, 200))) if rng.random() < 0.25 else pd.NaT
            appr.append((_, a)), exp.append((_, e)), wd.append((_, w))
    c["mlr_approved"] = pd.Series(dict(appr))
    c["mlr_expiry"] = pd.Series(dict(exp))
    c["withdrawn"] = pd.Series(dict(wd))
    c.loc[c.withdrawn >= c.mlr_expiry, "withdrawn"] = pd.NaT
    # planted event 7: two Brand B e-detail contents in IT whose MLR approval expires near the end of the period
    it = c[(c.market == "IT") & (c.type == "e-detail")].index[:2]
    c.loc[it, "brand"] = "Brand B"
    c.loc[it, "mlr_approved"] = [pd.Timestamp("2024-10-21"), pd.Timestamp("2024-11-03")]
    c.loc[it, "mlr_expiry"] = [pd.Timestamp("2026-10-21"), pd.Timestamp("2026-11-03")]
    c.loc[it, "withdrawn"] = pd.NaT
    c["end"] = c[["mlr_expiry", "withdrawn"]].min(axis=1)
    return c


def status_history(c):
    rows = []
    for r in c.itertuples():
        rows.append({"content_id": r.content_id, "status": "approved", "valid_from": r.mlr_approved, "valid_to": r.end})
        rows.append({"content_id": r.content_id, "status": "withdrawn" if pd.notna(r.withdrawn) else "expired",
                     "valid_from": r.end, "valid_to": pd.Timestamp("2099-12-31")})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ daily volumes
def offsets(dates):
    out = {}
    for m, tz in TZ.items():
        idx = pd.DatetimeIndex(dates + pd.Timedelta(hours=12)).tz_localize(tz)
        out[m] = pd.Series([x.utcoffset().total_seconds() / 3600 for x in idx], index=dates)
    return out


def daily_expected(dates, mk, hol, aug=SEASON[8]):
    rows = []
    for r in mk.itertuples():
        for d in dates:
            wd = d.weekday() < 5 and d not in hol[r.market]
            f = (1.0 if wd else (0.04 if d.weekday() >= 5 else 0.06)) * (aug if d.month == 8 else SEASON[d.month])
            if (d.month == 12 and d.day >= 22) or (d.month == 1 and d.day <= 2):
                f *= 0.35
            rows.append({"date": d, "market": r.market, "working_day": wd, "exp": r.target_hcps * 0.024 * f})
    return pd.DataFrame(rows)


def edetail_counts(mk, hol):
    dates = pd.date_range(START, END)
    d = daily_expected(dates, mk, hol)
    d["n"] = np.maximum(0, np.round(d.exp * rng.lognormal(0, 0.08, len(d)))).astype(int)
    # planted event 8: August -31% vs July (sessions), a seasonal dip; make it exact on the total
    jul, aug = d[d.date.dt.month == 7].n.sum(), d[d.date.dt.month == 8].n.sum()
    target = int(round(0.69 * jul))
    m8 = d.date.dt.month == 8
    scale = target / aug
    d.loc[m8, "n"] = np.floor(d.loc[m8, "n"] * scale).astype(int)
    short = target - d.loc[m8, "n"].sum()
    top = d[m8].sort_values("n", ascending=False).index[:short]
    d.loc[top, "n"] += 1
    aug_eff = SEASON[8] * scale
    truth(8, "False signal: August dip", "e-detail sessions Aug 2026 vs Jul 2026", round(target / jul - 1, 4))
    return d, aug_eff


def prior_year(mk, hol, aug_eff):
    dates = pd.date_range("2025-06-01", "2025-11-30")
    d = daily_expected(dates, mk, hol, aug_eff)
    d["n"] = np.maximum(0, np.round(d.exp * rng.lognormal(0, 0.08, len(d)))).astype(int)
    d["month"] = d.date.dt.strftime("%Y-%m")
    out = d.groupby(["month", "market"]).agg(edetail_sessions=("n", "sum"), working_days=("working_day", "sum")).reset_index()
    out["source"] = "Client P legacy monthly report (SIMULATED)"
    a = out[out.month == "2025-08"].edetail_sessions.sum() / out[out.month == "2025-07"].edetail_sessions.sum() - 1
    truth(8, "False signal: August dip", "same dip in Aug 2025 vs Jul 2025 (prior-year report)", round(a, 4))
    return out


# ------------------------------------------------------------------ events
def pick_hcp(h, market, n, spec_p=None):
    g = h[h.market == market]
    w = g.propensity.values.copy()
    if spec_p is not None:
        share = g.specialty.map(dict(zip(SPECS, spec_p))).values
        cnt = g.specialty.map(g.specialty.value_counts()).values
        w = w / g.groupby("specialty").propensity.transform("sum").values * share
    w = w / w.sum()
    return g.iloc[rng.choice(len(g), size=n, p=w)]


def active(c, market, typ, day):
    g = c[(c.market == market) & (c.type == typ) & (c.mlr_approved <= day) & (c.end > day)]
    return g


def edetail_sessions(counts, h, c, off):
    rows = []
    for r in counts[counts.n > 0].itertuples():
        cand = active(c, r.market, "e-detail", r.date)
        if cand.empty:
            continue
        hc = pick_hcp(h, r.market, r.n)
        start_local = r.date + pd.to_timedelta(9 * 3600 + rng.integers(0, 9 * 3600, r.n), unit="s")
        start = start_local - pd.Timedelta(hours=off[r.market][r.date])
        rows.append(pd.DataFrame({"market": r.market, "hcp_id": hc.hcp_id.values, "rep_id": hc.rep_id.values,
                                  "content_id": rng.choice(cand.content_id.values, r.n), "start": start}))
    s = pd.concat(rows, ignore_index=True)
    s = plant_expiry(s, h, c, off)
    s["n_slides"] = 2 + rng.poisson(4, len(s))
    return s


def plant_expiry(s, h, c, off):
    """Event 7: the two IT Brand B contents stay in use up to 19 days after MLR expiry: exactly 412 sessions."""
    planted = c[(c.market == "IT") & (c.brand == "Brand B") & (c.type == "e-detail")].iloc[:2]
    it = s[s.market == "IT"]
    picks = []
    quota = [230, 182]
    for (cid, exp), q in zip(planted[["content_id", "mlr_expiry"]].values, quota):
        win = it[(it.start >= exp) & (it.start < exp + pd.Timedelta(days=19))]
        win = win.drop([i for _, ix in picks for i in ix], errors="ignore")      # the two windows overlap
        idx = rng.choice(win.index, size=q, replace=False)
        picks.append((cid, idx))
        last = exp + pd.Timedelta(days=19) + pd.Timedelta(hours=8)       # last use exactly 19 days after expiry
        s.loc[idx[0], "start"] = last
    for cid, idx in picks:
        s.loc[idx, "content_id"] = cid
    truth(7, "Compliance: MLR expiry", "sessions on 2 IT Brand B contents after expiry", sum(quota))
    truth(7, "Compliance: MLR expiry", "max days used after expiry", 19)
    return s


def explode_sessions(s, channel):
    """session_start, slide_view x n, session_end; durations in whole seconds."""
    s = s.reset_index(drop=True)
    s["sid"] = np.arange(len(s))
    rep = np.repeat(s.index.values, s.n_slides.values)
    sl = s.loc[rep, ["sid", "start"]].reset_index(drop=True)
    sl["k"] = sl.groupby("sid").cumcount()
    dwell = np.clip(np.round(rng.lognormal(np.log(20), 0.6, len(sl))), 3, 600).astype(int)
    sl["dwell"] = dwell
    sl["offset"] = sl.groupby("sid").dwell.cumsum() - sl.dwell + 2          # first slide 2 s after start
    sl["ts"] = sl.start + pd.to_timedelta(sl.offset, unit="s")
    last = sl.groupby("sid").ts.max()
    s["last_slide"] = s.sid.map(last)
    s["end"] = s.last_slide + pd.to_timedelta(rng.integers(5, 31, len(s)), unit="s")   # normal close <= last + 30 s
    s["channel"] = channel
    return s, sl


def forgotten_tabs(s):
    """Event 5: forgotten tabs (> 30 min idle after the last slide) inflate naive engagement time by exactly +38%."""
    cap_end = s.last_slide + pd.Timedelta(seconds=30)
    n = int(0.38 * (s.end - s.start).dt.total_seconds().sum() // 3000)
    idx = rng.choice(s.index, n, replace=False)
    capped = (s.end - s.start).dt.total_seconds()
    capped.loc[idx] = (cap_end.loc[idx] - s.loc[idx, "start"]).dt.total_seconds()
    E = int(round(0.38 * capped.sum()))                  # total idle seconds above the capped end
    x = rng.exponential(1.0, n)
    extra = 1830 + np.floor(x / x.sum() * (E - 1830 * n)).astype(int)
    extra[0] += E - extra.sum()
    s.loc[idx, "end"] = cap_end.loc[idx] + pd.to_timedelta(extra, unit="s")
    naive = (s.end - s.start).dt.total_seconds().sum()
    cap2 = (np.minimum(s.end, cap_end) - s.start).dt.total_seconds().sum()
    truth(5, "KPI definition: idle sessions", "naive / capped engagement time - 1 (e-detail)", round(naive / cap2 - 1, 4))
    truth(5, "KPI definition: idle sessions", "sessions idle > 30 min", n)
    return s


def emails(h, c, mk, hol, off):
    rows = []
    dates = pd.date_range(START, END)
    for r in mk.itertuples():
        mix = SEND_MIX.get(r.market, DEFAULT_MIX)
        for d in dates:
            if d.weekday() >= 5 or d in hol[r.market]:
                continue
            cand = active(c, r.market, "approved-email", d)
            if cand.empty:
                continue
            f = (SEASON[d.month] if d.month != 8 else 0.75)
            n = int(rng.poisson(r.target_hcps * 0.062 * f))
            if n == 0:
                continue
            hc = pick_hcp(h, r.market, n, mix)
            sent_local = d + pd.to_timedelta(8 * 3600 + rng.integers(0, 2 * 3600, n), unit="s")
            rows.append(pd.DataFrame({"market": r.market, "hcp_id": hc.hcp_id.values, "specialty": hc.specialty.values,
                                      "content_id": rng.choice(cand.content_id.values, n),
                                      "sent": sent_local - pd.Timedelta(hours=off[r.market][d])}))
    e = pd.concat(rows, ignore_index=True)
    p_open = e.specialty.map(P_OPEN).values
    ctr = e.specialty.map(CTR_SEG).values * e.market.map(CTR_MULT).values
    e["opened"] = rng.random(len(e)) < p_open
    e["clicked"] = e.opened & (rng.random(len(e)) < ctr / p_open)
    e["open_ts"] = e.sent + pd.to_timedelta(np.round(rng.exponential(6 * 3600, len(e))) + 30, unit="s")
    e["click_ts"] = e.open_ts + pd.to_timedelta(rng.integers(5, 600, len(e)), unit="s")
    seg = e[e.market.isin(["DE", "PL"])].groupby(["market", "specialty"]).clicked.mean().unstack()
    tot = e[e.market.isin(["DE", "PL"])].groupby("market").clicked.mean()
    truth(4, "Simpson effect DE vs PL CTR", "overall CTR DE / PL", f"{tot['DE']:.4f} / {tot['PL']:.4f}")
    for sp in SPECS:
        truth(4, "Simpson effect DE vs PL CTR", f"CTR {sp} DE / PL", f"{seg.loc['DE', sp]:.4f} / {seg.loc['PL', sp]:.4f}")
    return e


def landing(e, c):
    """Each email click opens the market's landing page of the same brand (or any live landing page)."""
    k = e[e.clicked].copy()
    lp = c[c.type == "landing-page"]
    cids = []
    for r in k.itertuples():
        g = lp[(lp.market == r.market) & (lp.mlr_approved <= r.click_ts) & (lp.end > r.click_ts)]
        cids.append(rng.choice(g.content_id.values) if len(g) else None)
    k["content_id"] = cids
    k = k.dropna(subset=["content_id"])
    s = pd.DataFrame({"market": k.market.values, "hcp_id": k.hcp_id.values, "rep_id": None, "content_id": k.content_id.values,
                      "start": (k.click_ts + pd.Timedelta(seconds=4)).values, "n_slides": 1 + rng.poisson(1.2, len(k))})
    return s


def webinars(h, c, off):
    rows = []
    for r in c[c.type == "webinar"].itertuples():
        lo, hi = max(r.mlr_approved, START), min(r.end, END)
        weds = [d for d in pd.date_range(lo, hi) if d.weekday() == 2 and d.month not in (8,)]
        if not weds:
            continue
        for d in rng.choice(weds, size=min(4, len(weds)), replace=False):
            d = pd.Timestamp(d)
            n = int(rng.integers(20, 70))
            hc = pick_hcp(h, r.market, n).drop_duplicates("hcp_id")
            t0 = d + pd.Timedelta(hours=17) - pd.Timedelta(hours=off[r.market][d])
            rows.append(pd.DataFrame({"market": r.market, "hcp_id": hc.hcp_id.values, "content_id": r.content_id,
                                      "ts": t0 + pd.to_timedelta(rng.integers(-300, 900, len(hc)), unit="s"),
                                      "duration_s": rng.integers(600, 3600, len(hc))}))
    return pd.concat(rows, ignore_index=True)


def build_events(sess, slides, e, w):
    ev = []
    s = sess
    ev.append(pd.DataFrame({"ts": s.start, "market": s.market, "hcp_id": s.hcp_id, "content_id": s.content_id,
                            "channel": s.channel, "event_type": "session_start", "duration_s": np.nan, "rep_id": s.rep_id}))
    sl = slides.merge(s[["sid", "market", "hcp_id", "content_id", "channel", "rep_id"]], on="sid")
    ev.append(pd.DataFrame({"ts": sl.ts, "market": sl.market, "hcp_id": sl.hcp_id, "content_id": sl.content_id,
                            "channel": sl.channel, "event_type": "slide_view", "duration_s": sl.dwell.astype(float), "rep_id": sl.rep_id}))
    ev.append(pd.DataFrame({"ts": s.end, "market": s.market, "hcp_id": s.hcp_id, "content_id": s.content_id, "channel": s.channel,
                            "event_type": "session_end", "duration_s": (s.end - s.start).dt.total_seconds(), "rep_id": s.rep_id}))
    for col, typ, mask in [("sent", "email_sent", None), ("open_ts", "email_open", "opened"), ("click_ts", "email_click", "clicked")]:
        g = e if mask is None else e[e[mask]]
        ev.append(pd.DataFrame({"ts": g[col], "market": g.market, "hcp_id": g.hcp_id, "content_id": g.content_id,
                                "channel": "approved-email", "event_type": typ, "duration_s": np.nan, "rep_id": None}))
    ev.append(pd.DataFrame({"ts": w.ts, "market": w.market, "hcp_id": w.hcp_id, "content_id": w.content_id, "channel": "webinar",
                            "event_type": "webinar_join", "duration_s": w.duration_s.astype(float), "rep_id": None}))
    ev = pd.concat(ev, ignore_index=True)
    ev = ev[ev.ts < END + pd.Timedelta(days=1)].copy()          # opens after the as_of date are not yet in the source
    ev["ts"] = ev.ts.dt.floor("s")
    ev = ev.sort_values(["ts", "hcp_id", "event_type"]).reset_index(drop=True)
    ev.insert(0, "event_id", [f"EV{i + 1:07d}" for i in range(len(ev))])
    ev["updated_at"] = ev.ts + pd.to_timedelta(rng.integers(1, 91, len(ev)), unit="s")   # server receive time (UTC)
    return ev


def source_view(ev):
    """Turn clean events into the source table as the API serves it: string timestamps, RO bug, duplicates."""
    src = ev.copy()
    src["event_ts"] = src.ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # event 3: from 01/10/2026 (local), the RO device integration sends session_start / slide_view in local time without offset
    cut = pd.Timestamp("2026-10-01").tz_localize(TZ["RO"]).tz_convert("UTC").tz_localize(None)
    bug = (src.market == "RO") & src.event_type.isin(["session_start", "slide_view"]) & (src.ts >= cut)
    local = src.loc[bug, "ts"].dt.tz_localize("UTC").dt.tz_convert(TZ["RO"]).dt.tz_localize(None)
    src.loc[bug, "event_ts"] = local.dt.strftime("%Y-%m-%dT%H:%M:%S")
    truth(3, "Time zone: RO local time without offset", "RO events with naive local timestamps", int(bug.sum()))
    truth(3, "Time zone: RO local time without offset", "first day (local)", "2026-10-01")
    # event 1: the source API is down 14/09/2026 06:00-12:00 UTC; job v1 (run every 6 h) loses updated_at (03:00, 09:00]
    lost = (src.updated_at > "2026-09-14 03:00") & (src.updated_at <= "2026-09-14 09:00")
    truth(1, "Source outage", "API returns 500 (UTC, wall clock)", "2026-09-14 06:00-12:00")
    truth(1, "Source outage", "events lost by job v1 (updated_at 03:00-09:00]", int(lost.sum()))
    # event 2: after the outage the integration re-sends the late-morning events several times -> 3,214 duplicate rows
    orig = src[(src.updated_at > "2026-09-14 09:00") & (src.updated_at <= "2026-09-14 12:00")]
    k = rng.integers(1, 12, len(orig)).astype(float)
    k = np.floor(k / k.sum() * 3214).astype(int)
    k[: 3214 - k.sum()] += 1
    dup = orig.loc[np.repeat(orig.index.values, k)].copy()
    dup["updated_at"] = pd.Timestamp("2026-09-14 12:00") + pd.to_timedelta(rng.integers(1, 7200, len(dup)), unit="s")
    truth(2, "Duplicates after retries", "duplicate rows (same event_id)", len(dup))
    src = pd.concat([src, dup], ignore_index=True).sort_values(["updated_at", "event_id"]).reset_index(drop=True)
    src["updated_at"] = src.updated_at.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    cols = ["event_id", "event_ts", "market", "hcp_id", "content_id", "channel", "event_type", "duration_s", "rep_id", "updated_at"]
    return src[cols]


def point_in_time_truth(ev, c):
    ended = c[(c.end <= END) & (c.end >= START)]
    sess = ev[(ev.event_type == "session_start") & ev.content_id.isin(ended.content_id)]
    truth(6, "Leakage: current status filter", "contents ended (expired/withdrawn) during the period", len(ended))
    truth(6, "Leakage: current status filter", "sessions erased from past months by a current-status filter", len(sess))


def main():
    hol = holidays()
    mk = markets_table()
    h, reps = hcps_table(mk)
    br = brands()
    c = contents_table(br)
    c = c.merge(br[["brand", "therapeutic_area"]], on="brand")
    off = offsets(pd.date_range("2025-06-01", END + pd.Timedelta(days=1)))
    counts, aug_eff = edetail_counts(mk, hol)
    py = prior_year(mk, hol, aug_eff)
    sd = edetail_sessions(counts, h, c, off)
    sd, sl_d = explode_sessions(sd, "e-detail")
    sd = forgotten_tabs(sd)
    em = emails(h, c, mk, hol, off)
    sw, sl_w = explode_sessions(landing(em, c), "web")
    sw["sid"] += sd.sid.max() + 1
    sl_w["sid"] += sd.sid.max() + 1
    sess = pd.concat([sd, sw], ignore_index=True)
    slides = pd.concat([sl_d, sl_w], ignore_index=True)
    wb = webinars(h, c, off)
    ev = build_events(sess, slides, em, wb)
    point_in_time_truth(ev, c)
    src = source_view(ev)
    src.to_parquet(SIM / "events.parquet", index=False)
    mk.to_csv(SIM / "markets.csv", index=False)
    h.drop(columns="propensity").to_csv(SIM / "hcps.csv", index=False)
    c.drop(columns="end").to_csv(SIM / "contents.csv", index=False)
    status_history(c).to_csv(SIM / "content_status_history.csv", index=False)
    br.to_csv(SIM / "brands.csv", index=False)
    py.to_csv(SIM / "prior_year_monthly.csv", index=False)
    pd.DataFrame(TRUTH).to_csv(ROOT / "data" / "_hidden_truth.csv", index=False)
    print("events", len(ev), "source rows", len(src), "hcps", len(h), "contents", len(c), "sessions", len(sess))
    print(pd.DataFrame(TRUTH).to_string(index=False))


if __name__ == "__main__":
    main()
