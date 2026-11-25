# data/public: derived public files (PUBLIC DATA)

Built by `src/collect_public.py` and `src/collect_trials.py` on 25 Nov 2026. Enough to re-run the whole study without collecting again. No person names are kept.

| File | Source | Licence / attribution |
|---|---|---|
| `eurostat_physicians.csv` | Eurostat `hlth_rs_prs2`, practising physicians, latest year | Eurostat re-use policy, source: Eurostat |
| `ema_medicines.csv` | Medicines output report (xlsx), sheet `Medicine`; medicine names dropped; `area_group` added (keyword grouping) | Source: European Medicines Agency (re-use allowed with acknowledgement of EMA as the source) |
| `trials_recruiting.csv`, `trials_load_log.csv` | ClinicalTrials.gov API v2; fields NCTId, Condition, OverallStatus, StartDate, Phase only | U.S. National Library of Medicine |
| `npm_ewizard_cli_meta.json`, `npm_ewizard_cli_downloads.csv` | npm registry and download API (maintainers not kept) | public metadata |
| `holidays.csv` | Nager.Date public holidays 2025-2026, national only | Nager.Date (MIT) |
| `registry_estonia.json` | Estonian business register, autocomplete API (company fields only) | ariregister.rik.ee |
| `lever_posting.json`, `lever_postings.csv` | Lever postings API of Viseven (titles, locations, dates) | public job postings |
| `viseven_site_facts.json` | presence of keywords on 3 viseven.com pages (no text, no names) | as stated by Viseven |
