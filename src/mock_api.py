"""Local REST API of the fictional content platform of "Client P" (SIMULATED). Runs on 127.0.0.1 only.

It is a stand-in written for this case study: it is NOT the API of eWizard or of any Viseven product.
Standard library only (http.server). Start it in a second terminal and leave it running:
    python src/mock_api.py              (add --no-outage to switch the planted 14/09 outage off)

Auth      header `Authorization: Bearer <MOCK_API_TOKEN>`; a dummy token is generated at start and written to .env
Endpoints GET /health
          GET /v1/events?updated_since=<ISO>&updated_until=<ISO>&as_of=<ISO>&cursor=<c>&limit=500   (limit <= 5000)
              rows ordered by (updated_at, event_id); updated_since is exclusive, updated_until inclusive.
              as_of = the caller's clock (used to replay a year of scheduled runs); updated_until defaults to as_of.
          GET /v1/events/count?from=<ISO>&to=<ISO>[&group_by=day]
              rows and distinct event_ids (counted on their first updated_at) with updated_at in (from, to]
Errors    401 bad token · 400 bad parameter · 429 + Retry-After above 5 requests per second · 500 while the source
          is down (as_of in 2026-09-14 06:00-12:00 UTC, planted event 1)
"""
import argparse
import base64
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from common import API_HOST, API_PORT, ROOT, SIM

OUTAGE = ("2026-09-14T06:00:00Z", "2026-09-14T12:00:00Z")
RATE = 5
LOCK = threading.Lock()
HITS = defaultdict(deque)


def load():
    d = pd.read_parquet(SIM / "events.parquet").sort_values(["updated_at", "event_id"]).reset_index(drop=True)
    first = ~d.event_id.duplicated()
    d = d.astype(object).where(d.notna(), None)
    return d, d.updated_at.to_numpy(dtype=str), first.to_numpy()


def write_token():
    tok = "mock-" + secrets.token_hex(12)          # dummy value for the local API only
    p = ROOT / ".env"
    lines = [l for l in (p.read_text(encoding="utf-8").splitlines() if p.exists() else []) if not l.startswith("MOCK_API_TOKEN=")]
    p.write_text("\n".join(lines + [f"MOCK_API_TOKEN={tok}"]) + "\n", encoding="utf-8")
    return tok


def iso(v, name):
    if v is None:
        return None
    try:
        return pd.Timestamp(v).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        raise ValueError(f"invalid {name}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                     # quiet
        pass

    def send(self, code, body, headers=None):
        b = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def limited(self):
        now, ip = time.time(), self.client_address[0]
        with LOCK:
            q = HITS[ip]
            while q and now - q[0] > 1.0:
                q.popleft()
            if len(q) >= RATE:
                return True
            q.append(now)
        return False

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/health":
            return self.send(200, {"status": "ok", "rows": int(len(S.d))})
        if self.headers.get("Authorization") != f"Bearer {S.token}":
            return self.send(401, {"error": "invalid or missing token"})
        if self.limited():
            return self.send(429, {"error": "rate limit: 5 requests per second"}, {"Retry-After": "1"})
        try:
            if u.path == "/v1/events":
                return self.events(q)
            if u.path == "/v1/events/count":
                return self.count(q)
            return self.send(404, {"error": "not found"})
        except ValueError as e:
            return self.send(400, {"error": str(e)})

    def events(self, q):
        as_of = iso(q.get("as_of"), "as_of") or S.ua[-1]
        if S.outage and OUTAGE[0] <= as_of < OUTAGE[1]:
            return self.send(500, {"error": "upstream partition unavailable"})
        since = iso(q.get("updated_since"), "updated_since") or ""
        until = min(iso(q.get("updated_until"), "updated_until") or as_of, as_of)
        limit = int(q.get("limit", 500))
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be 1..5000")
        lo = int(np.searchsorted(S.ua, since, "right"))
        hi = int(np.searchsorted(S.ua, until, "right"))
        if q.get("cursor"):
            try:
                lo = max(lo, int(base64.urlsafe_b64decode(q["cursor"]).decode()))
            except Exception:
                raise ValueError("invalid cursor")
        j = min(lo + limit, hi)
        rows = S.d.iloc[lo:j].to_dict("records") if j > lo else []
        nxt = base64.urlsafe_b64encode(str(j).encode()).decode() if j < hi else None
        return self.send(200, {"data": rows, "returned": len(rows), "next_cursor": nxt, "as_of": as_of})

    def count(self, q):
        f, t = iso(q.get("from"), "from") or "", iso(q.get("to"), "to") or S.ua[-1]
        lo, hi = int(np.searchsorted(S.ua, f, "right")), int(np.searchsorted(S.ua, t, "right"))
        if q.get("group_by") == "day":
            day = pd.Series(S.ua[lo:hi]).str[:10]
            g = pd.DataFrame({"day": day, "first": S.first[lo:hi]}).groupby("day")["first"].agg(["size", "sum"])
            return self.send(200, {"from": f, "to": t, "days": [{"day": k, "rows": int(r["size"]), "distinct_event_ids": int(r["sum"])}
                                                               for k, r in g.iterrows()]})
        return self.send(200, {"from": f, "to": t, "rows": hi - lo, "distinct_event_ids": int(S.first[lo:hi].sum())})


class S:
    d = ua = first = token = None
    outage = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-outage", action="store_true")
    a = ap.parse_args()
    S.d, S.ua, S.first = load()
    S.token, S.outage = write_token(), not a.no_outage
    srv = ThreadingHTTPServer((API_HOST, API_PORT), Handler)
    print(f"mock API on http://{API_HOST}:{API_PORT} ({len(S.d):,} source rows, outage {'on' if S.outage else 'off'}); token in .env")
    srv.serve_forever()


if __name__ == "__main__":
    main()
