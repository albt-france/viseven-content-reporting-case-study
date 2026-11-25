"""Shared paths and constants. No personal data, no keys."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # raw downloads, cache only (not published)
PUBLIC = ROOT / "data" / "public"      # derived public files, enough to re-run everything
SIM = ROOT / "data" / "sim"            # simulated Client P source system (regenerated, seed 42)
OUT = ROOT / "data" / "output"         # results of SQL and checks
DB = ROOT / "data" / "warehouse.duckdb"
UA = {"User-Agent": "viseven-case-study/1.0"}
MARKETS = ["RO", "PL", "FR", "DE", "ES", "IT", "BG", "UA"]
COUNTRY = {"RO": "Romania", "PL": "Poland", "FR": "France", "DE": "Germany", "ES": "Spain", "IT": "Italy",
           "BG": "Bulgaria", "UA": "Ukraine"}
API_HOST, API_PORT = "127.0.0.1", 8765
COLLECTED = "25 Nov 2026"
for d in (RAW, PUBLIC, SIM, OUT):
    d.mkdir(parents=True, exist_ok=True)


def read_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


# Broad therapeutic areas from free text (EMA MeSH terms, trial conditions). First match wins; see docs/assumptions.md.
AREAS = [("Oncology", r"cancer|carcinoma|tumou?r|neoplasm|lymphoma|leukemia|leukaemia|myeloma|melanoma|sarcoma|glioma|oncolog"),
         ("Cardiovascular & metabolic", r"heart|cardi|hypertension|atrial|coronary|stroke|diabet|obes|lipid|cholesterol|metabolic|kidney|renal"),
         ("Neurology & psychiatry", r"alzheimer|parkinson|sclerosis|epilep|migraine|depress|schizo|neuro|dementia|bipolar|anxiety|pain"),
         ("Immunology & inflammation", r"arthritis|psoria|crohn|colitis|lupus|dermatitis|asthma|copd|eczema|inflamm|immun|urticaria"),
         ("Infectious diseases", r"hiv|hepatitis|covid|influenza|infection|vaccin|tubercul|sepsis|bacter|viral"),
         ("Rare & genetic", r"rare|orphan|syndrome|dystroph|hemophilia|haemophilia|fibrosis|sickle|amyloid")]


def area(text) -> str:
    import re
    t = str(text or "").lower()
    for name, rx in AREAS:
        if re.search(rx, t):
            return name
    return "Other"
