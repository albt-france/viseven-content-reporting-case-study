"""Real REST load: recruiting clinical trials with a site in each of the 8 markets (ClinicalTrials.gov API v2, PUBLIC DATA).

Adapted from an earlier pharma case study. The same rules as the simulated load (src/ingest.py) are applied to a real API:
- token pagination (`nextPageToken` -> `pageToken`), at most 1 request per second;
- retries with exponential backoff on 429 / 5xx / network errors, `Retry-After` respected;
- limited fields (`fields=`): only NCTId, Condition, OverallStatus, StartDate, Phase. Full records name investigators and
  contacts: they are never requested;
- completeness check: `totalCount` (asked with countTotal=true on the first page) must equal the rows received;
- cache: one raw JSONL file per market in data/raw/ct/, re-used on the next run (resume after an error).

Outputs: data/public/trials_recruiting.csv (one row per study x market) and data/public/trials_load_log.csv.
    python src/collect_trials.py
"""
import json
import time

import pandas as pd
import requests

from common import COUNTRY, MARKETS, PUBLIC, RAW, UA, area

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = "NCTId,Condition,OverallStatus,StartDate,Phase"
CT = RAW / "ct"
CT.mkdir(parents=True, exist_ok=True)

def get(params):
    for attempt in range(5):
        try:
            r = requests.get(API, params=params, headers=UA, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After", 2 ** attempt))
                time.sleep(wait)
                continue
            if r.status_code == 400:                   # invalid field names come back as plain text, not JSON
                raise ValueError(f"400: {r.text[:120]}")
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(2 ** attempt)
    raise RuntimeError("ClinicalTrials.gov unavailable after 5 attempts")


def load_market(m):
    path = CT / f"recruiting_{m}.jsonl"
    meta = CT / f"recruiting_{m}.meta.json"
    if path.exists() and meta.exists():                # cached: resume without calling the API again
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()], json.loads(meta.read_text())
    params = {"query.locn": COUNTRY[m], "filter.overallStatus": "RECRUITING", "pageSize": 1000,
              "countTotal": "true", "fields": FIELDS, "format": "json"}
    rows, token, pages, total, t0 = [], None, 0, None, time.time()
    while True:
        p = dict(params, pageToken=token) if token else params
        j = get(p)
        pages += 1
        if total is None:
            total = j.get("totalCount")
        rows.extend(j.get("studies", []))
        token = j.get("nextPageToken")
        time.sleep(1.0)                                # <= 1 request per second
        if not token:
            break
    info = {"market": m, "query": f"query.locn={COUNTRY[m]}, RECRUITING", "total_count": total, "received": len(rows),
            "pages": pages, "seconds": round(time.time() - t0, 1)}
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    meta.write_text(json.dumps(info))
    return rows, info


def main():
    out, log = [], []
    for m in MARKETS:
        rows, info = load_market(m)
        ids = set()
        for s in rows:
            ps = s.get("protocolSection", {})
            nct = ps.get("identificationModule", {}).get("nctId")
            ids.add(nct)
            cond = "; ".join(ps.get("conditionsModule", {}).get("conditions", []))
            out.append({"market": m, "nct_id": nct, "status": ps.get("statusModule", {}).get("overallStatus"),
                        "start_date": ps.get("statusModule", {}).get("startDateStruct", {}).get("date"),
                        "phase": "/".join(ps.get("designModule", {}).get("phases", []) or ["NA"]),
                        "area": area(cond), "conditions": cond[:200]})
        info["distinct_ids"] = len(ids)
        info["complete"] = info["total_count"] == info["received"] == len(ids)
        log.append(info)
        print(m, info["total_count"], info["received"], "OK" if info["complete"] else "CHECK")
    pd.DataFrame(out).to_csv(PUBLIC / "trials_recruiting.csv", index=False)
    pd.DataFrame(log).to_csv(PUBLIC / "trials_load_log.csv", index=False)


if __name__ == "__main__":
    main()
