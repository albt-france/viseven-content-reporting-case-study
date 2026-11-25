# Assumptions

## What is real and what is simulated
- **PUBLIC DATA** (real, read on 25 Nov 2026): Viseven's own pages and Lever job postings, the Estonian business register, npm metadata and downloads of `ewizard-cli`, Eurostat practising physicians, the EMA medicines report, ClinicalTrials.gov recruiting studies, Nager.Date public holidays.
- **SIMULATED**: everything about "Client P" (a fictional pharma company), its HCPs, contents, events, the local REST API and its incident. Nothing is data of Viseven, of its clients or of any real company. The local API is a stand-in written for this study; it is **not** the API of eWizard or of any Viseven product.

## Calibration of the simulation (`src/simulate_client_p.py`, seed 42)
| Item | Assumption | Source |
|---|---|---|
| Markets | RO, PL, FR, DE, ES, IT, BG, UA | Locations of Viseven's postings and EU markets (choice of the study) |
| HCPs | 6,000 in total, split by the weight of practising physicians (latest year, 2024). UA is not covered by Eurostat: assumed the size of RO | Eurostat `hlth_rs_prs2` |
| Segments | GP / Specialist / Pharmacist 40 / 45 / 15%, DE 20 / 70 / 10%, PL 60 / 25 / 15% | assumption (sets up the Simpson case) |
| Brands | Brand A = Oncology, Brand B = Cardiovascular & metabolic, Brand C = Immunology & inflammation: the 3 largest named areas of human medicines authorised 2023-2026 (92 / 41 / 33); content counts follow these weights | European Medicines Agency (keyword grouping of MeSH terms, see below) |
| Contents | 120 (45 e-detail, 40 approved email, 10 webinar, 25 landing page), one market each; MLR validity 12, 18 or 24 months; 25% of non-core contents withdrawn early | assumption |
| Volumes | about 0.024 e-detail sessions per HCP per working day; about 0.062 emails per HCP per working day; 20-70 HCPs per webinar | assumption |
| Seasonality | monthly factors, Christmas week x 0.35, weekends and public holidays almost no field activity | public holidays from Nager.Date |
| Prior year | Jun-Nov 2025 monthly e-detail totals from Client P's legacy report (simulated with the same model) | needed because event history starts in Dec 2025 |
| Server receive time | `updated_at` = event time + 1 to 90 s | assumption |

## Broad therapeutic areas
EMA MeSH terms and trial conditions are grouped by keywords into 6 broad areas (Oncology; Cardiovascular & metabolic; Neurology & psychiatry; Immunology & inflammation; Infectious diseases; Rare & genetic) plus Other (`AREAS` in `src/common.py`). First match wins. It is a rough grouping for context, not a medical classification.

## Reading limits
- EMA counts only medicines **still authorised**: older years are undercounted (survivor bias).
- ClinicalTrials.gov: a study counts in every market where it lists a site; `query.locn` matches location text.
- npm downloads of `ewizard-cli` include bots and CI: a public index of development activity, not a number of users or clients.
- The Eurostat EU27 total is empty in this table; countries are shown individually.
