"""Write and execute notebooks/viseven_data_analyst_case_study.ipynb (one notebook, the whole story, read-only on the outputs).

Order: real market -> API and load -> verification -> KPIs -> report -> incident -> improvements.
    python src/build_notebook.py        (after run_sql.py and check_workbook.py)
"""
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

from common import ROOT

NB = ROOT / "notebooks" / "viseven_data_analyst_case_study.ipynb"
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    md("# Viseven: content-engagement reports that clients can trust\n"
       "Independent case study based on public data · not affiliated with or endorsed by Viseven.\n\n"
       "**PUBLIC DATA**: Eurostat, European Medicines Agency, ClinicalTrials.gov, npm, public holidays. "
       "**SIMULATED**: the fictional pharma company *Client P* (8 markets, Dec 2025 - Nov 2026), its HCPs (identifiers only), "
       "contents and the local REST API. This notebook only reads the outputs built by the scripts (see README)."),
    code("import duckdb, pandas as pd\nfrom pathlib import Path\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
         "con = duckdb.connect(str(ROOT / 'data' / 'warehouse.duckdb'), read_only=True)\nq = lambda s: con.execute(s).df()\n"
         "out = lambda n: pd.read_csv(ROOT / 'data' / 'output' / f'{n}.csv')"),
    md("## 1. The real market (PUBLIC DATA)\nPractising physicians (Eurostat, 2024), recruiting trials by market (ClinicalTrials.gov REST load, "
       "`totalCount` checked), EU medicines still authorised by year (Source: European Medicines Agency; survivor bias)."),
    code("out('physicians')"),
    code("out('trials_by_market')[['market', 'recruiting_studies', 'oncology_pct', 'api_total_count', 'received', 'complete']]"),
    code("out('ema_by_year_area').query('year >= 2022').pivot_table(index='year', columns='area_group', values='medicines', fill_value=0)"),
    md("## 2. The API and the loads (SIMULATED)\nFull load to 01/09/2026, then the 6-hourly incremental job replayed as it ran in production (v1), "
       "then a backfill. Every run is logged."),
    code("q('SELECT * FROM out_load_runs')"),
    code("q(\"SELECT run_id, as_of, updated_since, status, watermark_after FROM load_runs WHERE status LIKE 'failed%'\")"),
    code("out('benchmark_load')[['scenario', 'requests', 'seconds', 'rows_loaded', 'lost_events']]"),
    md("## 3. Verification\nChecks C1-C8 before and after the backfill (`src/verify.py`)."),
    code("v = out('verification_checks')\nv.pivot(index='check', columns='run_label', values='status')[['before_backfill', 'after_backfill']]"),
    code("out('reconciliation_incident')"),
    code("out('timezone_check')"),
    md("## 4. KPIs\nEngagement time capped at the last slide + 30 s; CTR by segment (Simpson); point-in-time content status."),
    code("out('engagement_definition')"),
    code("out('simpson').pivot(index='segment', columns='market', values='ctr')"),
    code("out('simpson_standardised')"),
    code("out('point_in_time_restatement')"),
    md("## 5. The monthly report (October 2026)\nSame values as the Excel workbook (test T14)."),
    code("out('kpi_market').query(\"month == '2026-10'\")"),
    code("pd.read_csv(ROOT / 'data' / 'output' / 'workbook_check.csv').assign(diff=lambda d: d.excel - d.python).describe().loc[['count', 'max']]"),
    md("## 6. Incident and compliance\nOutage of 14/09/2026 (v1 vs v2), sessions after MLR expiry, and the August dip read against working days."),
    code("out('benchmark_load').query(\"scenario.str.startswith('incident')\")[['scenario', 'requests', 'rows_loaded', 'lost_events']]"),
    code("out('compliance')[['content_id', 'market', 'brand', 'mlr_expiry', 'sessions', 'hcps', 'max_days_after_expiry']]"),
    code("out('august_check')"),
    md("## 7. Tests and improvements\nAll assertions of `sql/99_tests.sql`. Proposals with before / after: `docs/report_improvements.md`."),
    code("q('SELECT * FROM test_results ORDER BY test')"),
]


def main():
    nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
    ExecutePreprocessor(timeout=300, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
    NB.write_text(nbf.writes(nb), encoding="utf-8")
    print("written and executed", NB)


if __name__ == "__main__":
    main()
