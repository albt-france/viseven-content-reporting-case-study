"""Check the workbook: the values Excel computed (cached) vs a Python recomputation from the Data sheet vs SQL.

1. Reads KPI!B4 (must be 2026-10 for the test) and the KPI table as computed by Excel (data_only).
2. Recomputes the same KPIs in Python from the Data sheet (fallback when no spreadsheet program recalculated the file).
3. Reads the Verification sheet status (all controls must be OK) and scans for formula errors (#NAME?, #VALUE!...).
4. Writes the values into DuckDB table workbook_kpi and re-runs sql/99_tests.sql (test T14: zero difference).
    python src/check_workbook.py
"""
import duckdb
import pandas as pd
from openpyxl import load_workbook

from common import DB, MARKETS, OUT, ROOT
from run_sql import run

PATH = ROOT / "excel" / "client_p_monthly_report.xlsx"


def python_kpis(month):
    d = pd.read_excel(PATH, sheet_name="Data")
    a = d[(d.Month == month) & (d.Segment == "All")]
    out = []
    for mk in MARKETS:
        x = a[a.Market == mk].set_index("Channel")
        sess = x.loc["e-detail", "Sessions"]
        out += [("reached", mk, x.loc["All", "HCPs reached"]), ("edetail_sessions", mk, sess),
                ("engaged_min", mk, x.loc["e-detail", "Engaged s (capped)"] / sess / 60),
                ("ctr", mk, x.loc["approved-email", "Emails clicked"] / x.loc["approved-email", "Emails sent"])]
    return pd.DataFrame(out, columns=["metric", "market", "python"])


def main():
    wb = load_workbook(PATH, data_only=True)
    k = wb["KPI"]
    month = k["B4"].value
    rows = []
    for r in range(7, 15):
        mk = k[f"A{r}"].value
        rows += [("reached", mk, k[f"C{r}"].value), ("edetail_sessions", mk, k[f"F{r}"].value),
                 ("engaged_min", mk, k[f"G{r}"].value), ("ctr", mk, k[f"K{r}"].value)]
    xl = pd.DataFrame(rows, columns=["metric", "market", "excel"])
    py = python_kpis(month)
    cmp_ = xl.merge(py, on=["metric", "market"])
    cached = cmp_.excel.notna().all()
    errors = [f"{ws.title}!{c.coordinate}" for ws in wb for row in ws.iter_rows() for c in row
              if isinstance(c.value, str) and c.value.startswith("#") and c.value.rstrip("!?0/").isupper()]
    v = wb["Verification"]
    status = [v.cell(row=r, column=5).value for r in range(5, v.max_row + 1) if v.cell(row=r, column=1).value]
    overall = next((s for s in reversed(status) if s in ("OK", "CHECK")), None)
    if cached:
        diff = (cmp_.excel - cmp_.python).abs().max()
        values = cmp_.rename(columns={"excel": "value"})[["metric", "market", "value"]]
        print(f"Excel values cached: yes · max |Excel - Python| = {diff:.2e} · formula errors: {len(errors)} · Verification: {overall}")
    else:
        values = cmp_.rename(columns={"python": "value"})[["metric", "market", "value"]]
        print("No cached values (file not recalculated): using the Python recomputation; open the file in Excel to see them.")
    con = duckdb.connect(str(DB))
    con.execute("CREATE OR REPLACE TABLE workbook_kpi AS SELECT metric, market, CAST(value AS DOUBLE) AS value FROM values")
    con.close()
    cmp_.to_csv(OUT / "workbook_check.csv", index=False)
    if month != "2026-10":
        print("KPI!B4 is", month, "- set it back to 2026-10 for test T14")
    res = run(["99"])
    assert not errors, errors[:5]


if __name__ == "__main__":
    main()
