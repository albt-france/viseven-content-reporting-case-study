"""Collect the small public sources (PUBLIC DATA). Every request is cached in data/raw/ and re-used.

Sources (all read 25 Nov 2026):
- Eurostat hlth_rs_prs2: practising physicians by country (unit NR and per 100,000 inhabitants).
- European Medicines Agency, medicines output report (xlsx). Source: European Medicines Agency.
- npm registry: public metadata and daily downloads of the `ewizard-cli` package (maintainers are NOT kept).
- Nager.Date: public holidays 2025-2026 for the 8 markets.
- Estonian business register (autocomplete API): company name, code, status, city only (no officers are queried).
- Lever postings API: the Data Analyst posting and the count of open postings (no person names kept).
- viseven.com: 3 pages, 1 request every 3 s; only keyword presence is stored (the pages name people: never stored).

Outputs in data/public/ (derived, no person names).
    python src/collect_public.py
"""
import json
import re
import time
from datetime import date

import pandas as pd
import requests

from common import MARKETS, PUBLIC, RAW, UA, area

S = requests.Session()
S.headers.update(UA)


def get(url, name, params=None, binary=False, pause=0.5):
    """GET with a file cache in data/raw/."""
    path = RAW / name
    if path.exists():
        return path.read_bytes() if binary else path.read_text(encoding="utf-8")
    r = S.get(url, params=params, timeout=60)
    r.raise_for_status()
    time.sleep(pause)
    if binary:
        path.write_bytes(r.content)
        return r.content
    path.write_text(r.text, encoding="utf-8")
    return r.text


def eurostat():
    geos = [g for g in MARKETS if g != "UA"] + ["EU27_2020"]
    params = [("wstatus", "PRACT"), ("med_spec", "PHYS"), ("sinceTimePeriod", "2019")] + [("geo", g) for g in geos]
    j = json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/hlth_rs_prs2",
                       "eurostat_hlth_rs_prs2.json", params))
    ids, size = j["id"], j["size"]
    cats = {d: {v: k for k, v in j["dimension"][d]["category"]["index"].items()} for d in ids}
    rows = []
    for flat, val in j["value"].items():
        idx, rest = [], int(flat)
        for s in reversed(size):                       # index = row-major combination of id x size
            idx.append(rest % s)
            rest //= s
        rec = {d: cats[d][i] for d, i in zip(ids, reversed(idx))}
        rec["value"] = val
        rows.append(rec)
    d = pd.DataFrame(rows)
    d = d.pivot_table(index=["geo", "time"], columns="unit", values="value").reset_index()
    d = d.rename(columns={"NR": "physicians", "P_HTHAB": "per_100k", "HAB_P": "inhabitants_per_physician"})
    d["time"] = d.time.astype(int)
    latest = d.dropna(subset=["physicians"]).sort_values("time").groupby("geo").tail(1)
    latest = latest[["geo", "time", "physicians", "per_100k"]].rename(columns={"geo": "market", "time": "year"})
    latest.to_csv(PUBLIC / "eurostat_physicians.csv", index=False)
    eu = d[(d.geo == "EU27_2020") & (d.time == 2023)]
    print("eurostat", latest.shape, "EU27 2023 empty:", eu.physicians.isna().all() if len(eu) else True)


def ema():
    raw = get("https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx",
              "ema_medicines_report.xlsx", binary=True)
    d = pd.read_excel(RAW / "ema_medicines_report.xlsx", sheet_name="Medicine", header=8)
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    keep = {"Category": "category", "Medicine status": "status", "Therapeutic area (MeSH)": "therapeutic_area",
            "Orphan medicine": "orphan", "Biosimilar": "biosimilar", "Generic or hybrid": "generic",
            "Marketing authorisation date": "authorisation_date"}
    miss = [k for k in keep if k not in d.columns]
    if miss:                                   # tolerate small renames: match on the first word
        for k in miss:
            cand = [c for c in d.columns if c.lower().startswith(k.lower().split()[0])]
            if cand:
                keep[cand[0]] = keep.pop(k)
    d = d[list(keep)].rename(columns=keep)          # medicine names are not kept: not needed
    d["authorisation_date"] = pd.to_datetime(d.authorisation_date.astype(str).str.strip(), format="%d/%m/%Y", errors="coerce")
    d["area_group"] = d.therapeutic_area.map(area)
    d.to_csv(PUBLIC / "ema_medicines.csv", index=False)
    h = d[(d.category == "Human") & (d.status == "Authorised")]
    print("ema", len(raw), d.shape, "human authorised", len(h), h.authorisation_date.dt.year.value_counts().sort_index().tail(4).to_dict())


def npm():
    meta = json.loads(get("https://registry.npmjs.org/ewizard-cli", "npm_ewizard_cli.json"))
    info = {"package": "ewizard-cli", "license": meta.get("license"), "versions": len(meta.get("versions", {})),
            "created": meta["time"]["created"][:10], "modified": meta["time"]["modified"][:10]}
    (PUBLIC / "npm_ewizard_cli_meta.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    dl = json.loads(get("https://api.npmjs.org/downloads/range/2025-11-01:2026-10-31/ewizard-cli", "npm_downloads.json"))
    d = pd.DataFrame(dl["downloads"])
    d.to_csv(PUBLIC / "npm_ewizard_cli_downloads.csv", index=False)
    print("npm", info, len(d), "days", int(d.downloads.sum()), "downloads")


def holidays():
    rows = []
    for y in (2025, 2026):
        for m in MARKETS:
            j = json.loads(get(f"https://date.nager.at/api/v3/PublicHolidays/{y}/{m}", f"nager_{y}_{m}.json"))
            for h in j:
                if h.get("global", True):              # national holidays only
                    rows.append({"market": m, "date": h["date"], "name": h["name"]})
    d = pd.DataFrame(rows).drop_duplicates(["market", "date"])
    d.to_csv(PUBLIC / "holidays.csv", index=False)
    print("holidays", d.shape)


def registry():
    j = json.loads(get("https://ariregister.rik.ee/est/api/autocomplete", "ariregister_12627365.json", {"q": "12627365"}))
    rec = j["data"][0] if isinstance(j, dict) and j.get("data") else j[0]
    out = {"name": rec.get("name"), "reg_code": str(rec.get("reg_code")), "status": rec.get("status"),
           "legal_address": rec.get("legal_address") or rec.get("address"), "source": "ariregister.rik.ee", "read": "2026-11-25"}
    (PUBLIC / "registry_estonia.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("registry", out["name"], out["reg_code"], out["status"])


def lever():
    p = json.loads(get("https://api.lever.co/v0/postings/viseven/ecb4d58c-d8f7-40be-b359-c8faef089b1e", "lever_posting.json"))
    out = {"title": p["text"], "categories": p.get("categories"), "country": p.get("country"),
           "workplaceType": p.get("workplaceType"), "createdAt": pd.to_datetime(p["createdAt"], unit="ms").isoformat(),
           "lists": [{"heading": l["text"], "items": re.sub(r"<[^>]+>", "|", l["content"]).split("|")} for l in p.get("lists", [])]}
    out["lists"] = [{"heading": l["heading"], "items": [i.strip() for i in l["items"] if i.strip()]} for l in out["lists"]]
    (PUBLIC / "lever_posting.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    allp = json.loads(get("https://api.lever.co/v0/postings/viseven?mode=json", "lever_all.json"))
    d = pd.DataFrame([{"title": x["text"], "location": x.get("categories", {}).get("location"),
                       "country": x.get("country"), "created": pd.to_datetime(x["createdAt"], unit="ms").date()} for x in allp])
    d.to_csv(PUBLIC / "lever_postings.csv", index=False)
    print("lever", out["title"], out["country"], out["createdAt"], "| postings:", len(d), "distinct titles:", d.title.nunique())


def site():
    pages = {"home": "https://viseven.com/", "careers": "https://viseven.com/careers/",
             "privacy": "https://viseven.com/privacy-policy/"}
    words = ["AI-powered", "Pharma Marketing", "eWizard", "eVa", "Kheiron", "Lexi", "life sciences", "MLR", "omnichannel",
             "Viseven Europe OÜ", "Viseven Europe LLC", "Viseven USA LLC", "12627365", "38428784", "lever.co"]
    facts = {}
    for k, u in pages.items():
        html = get(u, f"viseven_{k}.html", pause=3.0)          # 1 request every 3 s, no query strings
        text = re.sub(r"<[^>]+>", " ", html)
        facts[k] = {"url": u, "read": "2026-11-25", "contains": {w: (w.lower() in text.lower()) for w in words}}
    (PUBLIC / "viseven_site_facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False), encoding="utf-8")
    print("site", {k: sum(v["contains"].values()) for k, v in facts.items()})


if __name__ == "__main__":
    for f in (eurostat, ema, npm, holidays, registry, lever, site):
        try:
            f()
        except Exception as e:                          # one source failing must not block the others
            print("FAILED", f.__name__, type(e).__name__, str(e)[:200])
    print("done", date.today())
