"""Build the Client P monthly report workbook: excel/client_p_monthly_report.xlsx (SIMULATED).

Every KPI is a real Excel formula (SUMIFS, COUNTIFS, XLOOKUP, IFERROR, LET) over the Data sheet; only Data, the
compliance list and the SQL control totals are values. Choose the month in KPI!B4.
Recalculation: Excel (pywin32, one attempt) -> LibreOffice headless -> otherwise the values compute when the file is
opened (src/check_workbook.py recomputes them in Python). Document metadata are emptied afterwards (zip level).
    python src/build_workbook.py
"""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import DB, MARKETS, OUT, ROOT

XL = ROOT / "excel"
XL.mkdir(exist_ok=True)
PATH = XL / "client_p_monthly_report.xlsx"
HEAD = PatternFill("solid", fgColor="E3EEFB")
SIMF = PatternFill("solid", fgColor="FBE9E0")
INPUT = PatternFill("solid", fgColor="FFF4C2")
RED = PatternFill("solid", fgColor="F6D3D3")
GREEN = PatternFill("solid", fgColor="D8F0E3")
B = Font(bold=True)
TITLE = Font(bold=True, size=14)
MONTH = "2026-10"
DATA_COLS = ["Month", "Market", "Channel", "Segment", "HCPs targeted", "Suppressed (<5 HCPs)", "HCPs active", "HCPs reached",
             "Sessions", "Engaged s (capped)", "Engaged s (naive)", "Emails sent", "Emails opened", "Emails clicked", "Webinar joins"]
COL = {n: get_column_letter(i + 1) for i, n in enumerate(DATA_COLS)}


def q(sql):
    con = duckdb.connect(str(DB), read_only=True)
    d = con.execute(sql).df()
    con.close()
    return d


def header(ws, row, cols, fill=HEAD, col0=1):
    for j, c in enumerate(cols):
        cell = ws.cell(row=row, column=col0 + j, value=c)
        cell.font, cell.fill = B, fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, w):
    for j, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(j)].width = x


def tag(ws, text="SIMULATED · fictional Client P · not data of Viseven or of any company"):
    ws["A2"] = text
    ws["A2"].fill, ws["A2"].font = SIMF, Font(bold=True, color="9A3B12")


def sif(col, month, market, channel, segment):
    c = COL[col]
    return (f'SUMIFS(Data!${c}:${c},Data!$A:$A,{month},Data!$B:$B,{market},'
            f'Data!$C:$C,"{channel}",Data!$D:$D,"{segment}")')


def data_sheet(wb, d):
    ws = wb.create_sheet("Data")
    ws["A1"] = "Monthly aggregates by market, channel and HCP segment (from sql/04_kpi.sql). 'All' rows hold distinct HCP counts."
    ws.delete_rows(1)
    header(ws, 1, DATA_COLS)
    d = d.astype(object).where(d.notna(), None)
    for r in d.itertuples(index=False):
        ws.append([bool(v) if k == 5 else (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in enumerate(r)])
    ws.freeze_panes = "A2"
    widths(ws, [9, 8, 15, 11] + [11] * 11)
    return len(d)


def kpi_sheet(wb, months):
    ws = wb.create_sheet("KPI", 1)
    ws["A1"] = "Client P · monthly content-engagement report"
    ws["A1"].font = TITLE
    tag(ws)
    ws["A4"], ws["B4"] = "Month", MONTH
    ws["A4"].font, ws["B4"].fill, ws["B4"].font = B, INPUT, B
    dv = DataValidation(type="list", formula1=f'"{",".join(months)}"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B4")
    ws["C4"] = "← choose a month (yellow cell). Activity counts only on content MLR-approved at the time of the event."
    cols = ["Market", "HCPs targeted", "HCPs reached", "Coverage", "Frequency (interactions / reached HCP)", "E-detail sessions",
            "Engagement min / session (capped)", "Engagement min / session (naive, old)", "Emails sent", "Open rate", "Click-through rate",
            "Webinar joins", "Practising physicians (Eurostat)"]
    header(ws, 6, cols)
    m = "$B$4"
    for i, mk in enumerate(MARKETS + ["Total"]):
        r = 7 + i
        mref = f"$A{r}" if mk != "Total" else '"*"'
        ws[f"A{r}"] = mk
        if mk == "Total":
            ws[f"B{r}"] = "=SUM(B7:B14)"
            ws[f"C{r}"] = "=SUM(C7:C14)"
            ws[f"F{r}"] = "=SUM(F7:F14)"
            ws[f"I{r}"] = "=SUM(I7:I14)"
            ws[f"L{r}"] = "=SUM(L7:L14)"
            ws[f"M{r}"] = "=SUM(M7:M14)"
            for c in "ABCDEFGHIJKLM":
                ws[f"{c}{r}"].font = B
        else:
            ws[f"B{r}"] = f"={sif('HCPs targeted', m, mref, 'All', 'All')}"
            ws[f"C{r}"] = f"={sif('HCPs reached', m, mref, 'All', 'All')}"
            ws[f"F{r}"] = f"={sif('Sessions', m, mref, 'e-detail', 'All')}"
            ws[f"I{r}"] = f"={sif('Emails sent', m, mref, 'approved-email', 'All')}"
            ws[f"L{r}"] = f"={sif('Webinar joins', m, mref, 'webinar', 'All')}"
            ws[f"M{r}"] = f'=IFERROR(_xlfn.XLOOKUP($A{r},By_market!$A$22:$A$29,By_market!$B$22:$B$29),"n/a")'
        ws[f"D{r}"] = f"=IFERROR(C{r}/B{r},0)"
        ws[f"E{r}"] = (f"=_xlfn.LET(_xlpm.n,{sif('Sessions', m, mref, 'All', 'All')}+{sif('Emails opened', m, mref, 'All', 'All')}"
                       f"+{sif('Webinar joins', m, mref, 'All', 'All')},IFERROR(_xlpm.n/C{r},0))")
        ws[f"G{r}"] = f"=_xlfn.LET(_xlpm.e,{sif('Engaged s (capped)', m, mref, 'e-detail', 'All')},_xlpm.n,F{r},IFERROR(_xlpm.e/_xlpm.n/60,0))"
        ws[f"H{r}"] = f"=_xlfn.LET(_xlpm.e,{sif('Engaged s (naive)', m, mref, 'e-detail', 'All')},_xlpm.n,F{r},IFERROR(_xlpm.e/_xlpm.n/60,0))"
        ws[f"J{r}"] = f"=IFERROR({sif('Emails opened', m, mref, 'approved-email', 'All')}/I{r},0)"
        ws[f"K{r}"] = f"=IFERROR({sif('Emails clicked', m, mref, 'approved-email', 'All')}/I{r},0)"
        for c, fmt in [("D", "0.0%"), ("E", "0.00"), ("G", "0.00"), ("H", "0.00"), ("J", "0.0%"), ("K", "0.0%"), ("M", "#,##0")]:
            ws[f"{c}{r}"].number_format = fmt
    ws["A17"] = "Rows checked against SQL in the Verification sheet. Groups of fewer than 5 HCPs are suppressed in Data (blank)."
    ws["A18"] = '=COUNTIFS(Data!$A:$A,$B$4,Data!$F:$F,TRUE)&" suppressed cell(s) this month (primary + secondary suppression)"'
    ws.freeze_panes = "B7"
    widths(ws, [10, 11, 11, 10, 14, 11, 14, 14, 10, 9, 10, 10, 14])
    ws.row_dimensions[6].height = 48


def by_market_sheet(wb, months, phys):
    ws = wb.create_sheet("By_market")
    ws["A1"] = "E-detail sessions and capped engagement time by month and market"
    ws["A1"].font = TITLE
    tag(ws)
    header(ws, 4, ["Month"] + MARKETS + ["Total"])
    for i, mo in enumerate(months):
        r = 5 + i
        ws[f"A{r}"] = mo
        for j, mk in enumerate(MARKETS):
            c = get_column_letter(2 + j)
            ws[f"{c}{r}"] = f'={sif("Sessions", f"$A{r}", f"{c}$4", "e-detail", "All")}'
        ws[f"J{r}"] = f"=SUM(B{r}:I{r})"
    ws["A20"] = "Market reference (PUBLIC DATA: Eurostat hlth_rs_prs2, practising physicians, latest year; UA not covered)"
    header(ws, 21, ["Market", "Practising physicians", "Year", "Client P target HCPs (SIMULATED)"])
    for i, r in enumerate(phys.itertuples()):
        ws.append([r.market, r.physicians if pd.notna(r.physicians) else None, r.year if pd.notna(r.year) else None, r.client_p_hcps_simulated])
    header(ws, 32, ["Month"] + MARKETS)
    ws["A31"] = "Engagement minutes per e-detail session (capped), LET formula"
    for i, mo in enumerate(months):
        r = 33 + i
        ws[f"A{r}"] = mo
        for j, mk in enumerate(MARKETS):
            c = get_column_letter(2 + j)
            ws[f"{c}{r}"] = (f'=_xlfn.LET(_xlpm.e,{sif("Engaged s (capped)", f"$A{r}", f"{c}$32", "e-detail", "All")},'
                             f'_xlpm.n,{sif("Sessions", f"$A{r}", f"{c}$32", "e-detail", "All")},IFERROR(_xlpm.e/_xlpm.n/60,0))')
            ws[f"{c}{r}"].number_format = "0.00"
    widths(ws, [10] + [10] * 9)


def segments_sheet(wb):
    ws = wb.create_sheet("Segments")
    ws["A1"] = "Email click-through rate by market and HCP segment, Dec 2025 - Nov 2026 (read the segments before ranking markets)"
    ws["A1"].font = TITLE
    tag(ws)
    header(ws, 4, ["Market", "Segment", "Emails sent", "Clicks", "CTR", "Share of the market's sends"])
    segs = ["GP", "Specialist", "Pharmacist"]
    r = 5
    for mk in MARKETS:
        first = r
        for sg in segs + ["All"]:
            ws[f"A{r}"], ws[f"B{r}"] = mk, sg
            ws[f"C{r}"] = f'={sif("Emails sent", chr(34) + "*" + chr(34), f"$A{r}", "approved-email", sg)}'
            ws[f"D{r}"] = f'={sif("Emails clicked", chr(34) + "*" + chr(34), f"$A{r}", "approved-email", sg)}'
            ws[f"E{r}"] = f"=IFERROR(D{r}/C{r},0)"
            ws[f"F{r}"] = f"=IFERROR(C{r}/C${first + 3},0)"
            ws[f"E{r}"].number_format = ws[f"F{r}"].number_format = "0.0%"
            if sg == "All":
                for c in "ABCDEF":
                    ws[f"{c}{r}"].font = B
            r += 1
    end = r - 1
    r += 1
    ws[f"A{r}"] = "Segment mix of all sends (weights) and mix-standardised CTR"
    ws[f"A{r}"].font = B
    r += 1
    header(ws, r, ["Segment", "Weight (share of all sends)"])
    wrow = {}
    for sg in segs:
        r += 1
        wrow[sg] = r
        ws[f"A{r}"] = sg
        ws[f"B{r}"] = f'=IFERROR(SUMIFS($C$5:$C${end},$B$5:$B${end},A{r})/SUMIFS($C$5:$C${end},$B$5:$B${end},"All"),0)'
        ws[f"B{r}"].number_format = "0.0%"
    r += 2
    header(ws, r, ["Market", "CTR as reported", "CTR at the same segment mix", "Rank as reported", "Rank at same mix"])
    top = r + 1
    for i, mk in enumerate(MARKETS):
        r += 1
        base = 5 + i * 4
        ws[f"A{r}"] = mk
        ws[f"B{r}"] = f"=E{base + 3}"
        ws[f"C{r}"] = ("=_xlfn.LET(" + ",".join(f"_xlpm.{s[0].lower()},E{base + k}*$B${wrow[s]}" for k, s in enumerate(segs))
                       + ",_xlpm.g+_xlpm.s+_xlpm.p)")
        ws[f"D{r}"] = f"=RANK(B{r},$B${top}:$B${top + 7})"
        ws[f"E{r}"] = f"=RANK(C{r},$C${top}:$C${top + 7})"
        ws[f"B{r}"].number_format = ws[f"C{r}"].number_format = "0.00%"
    r += 2
    ws[f"A{r}"] = ("Reading: DE has a lower CTR than PL overall, but a higher CTR in every segment. DE sends mostly to specialists, "
                   "who click less (Simpson's paradox). Compare markets at the same mix, not on the raw total.")
    widths(ws, [10, 12, 12, 10, 10, 14])


def compliance_sheet(wb, comp):
    ws = wb.create_sheet("Compliance")
    ws["A1"] = "Content used after its MLR expiry or withdrawal (alert to raise with the client; no regulatory advice)"
    ws["A1"].font = TITLE
    tag(ws)
    cols = ["Content", "Market", "Brand", "Type", "MLR expiry", "Sessions after expiry", "HCPs (>= 5)", "First use after expiry",
            "Last use", "Days used after expiry", "Status"]
    header(ws, 4, cols)
    for i, r in enumerate(comp.itertuples()):
        x = 5 + i
        ws.append([r.content_id, r.market, r.brand, r.type, r.mlr_expiry, r.sessions, r.hcps, r.first_use_after_end, r.last_use])
        ws[f"J{x}"] = f"=I{x}-E{x}"
        ws[f"K{x}"] = f'=IF(J{x}>0,"ALERT","OK")'
        for c in "EHI":
            ws[f"{c}{x}"].number_format = "yyyy-mm-dd"
    last = 4 + max(len(comp), 1)
    ws.conditional_formatting.add(f"K5:K{last}", CellIsRule(operator="equal", formula=['"ALERT"'], fill=RED))
    ws.conditional_formatting.add(f"J5:J{last}", CellIsRule(operator="greaterThan", formula=["0"], fill=RED))
    ws[f"A{last + 2}"] = "Total sessions after expiry"
    ws[f"F{last + 2}"] = f"=SUM(F5:F{last})"
    ws[f"A{last + 3}"] = "Contents in alert"
    ws[f"F{last + 3}"] = f'=COUNTIFS(K5:K{last},"ALERT")'
    ws[f"A{last + 5}"] = ("These sessions are excluded from the KPIs (activity counts only on content approved at the time of the event) "
                          "and listed here so the client can act.")
    widths(ws, [10, 8, 9, 10, 12, 12, 10, 14, 12, 12, 9])


def verification_sheet(wb, ctl, checks):
    ws = wb.create_sheet("Verification")
    ws["A1"] = "Control totals: workbook formulas vs SQL (sql/04_kpi.sql). OK when the difference is 0."
    ws["A1"].font = TITLE
    tag(ws)
    header(ws, 4, ["Control", "SQL value", "Workbook formula", "Difference", "Status"])
    for i, r in enumerate(ctl):
        x = 5 + i
        ws[f"A{x}"], ws[f"B{x}"], ws[f"C{x}"] = r[0], r[1], r[2]
        ws[f"D{x}"] = f"=C{x}-B{x}"
        ws[f"E{x}"] = f'=IF(ABS(D{x})<0.001,"OK","CHECK")'
    last = 4 + len(ctl)
    ws.conditional_formatting.add(f"E5:E{last}", CellIsRule(operator="equal", formula=['"OK"'], fill=GREEN))
    ws.conditional_formatting.add(f"E5:E{last}", CellIsRule(operator="equal", formula=['"CHECK"'], fill=RED))
    ws[f"A{last + 1}"] = "All controls"
    ws[f"E{last + 1}"] = f'=IF(COUNTIFS(E5:E{last},"OK")={len(ctl)},"OK","CHECK")'
    ws[f"A{last + 1}"].font = ws[f"E{last + 1}"].font = B
    r0 = last + 4
    ws[f"A{r0 - 1}"] = "Data checks of the load (src/verify.py, after the backfill of 14/09/2026)"
    ws[f"A{r0 - 1}"].font = B
    header(ws, r0, ["Check", "Rule", "Observed", "Status", "Action"])
    for i, r in enumerate(checks.itertuples()):
        x = r0 + 1 + i
        for j, v in enumerate([r.check, r.rule, r.observed, r.status, r.action]):
            ws.cell(row=x, column=1 + j, value=v)
    ws.conditional_formatting.add(f"D{r0 + 1}:D{r0 + len(checks)}", FormulaRule(formula=[f'D{r0 + 1}<>"PASS"'], fill=RED))
    widths(ws, [46, 38, 40, 12, 60])


def readme_and_defs(wb):
    ws = wb.active
    ws.title = "README"
    lines = [("Client P monthly content-engagement report", TITLE),
             ("SIMULATED data for a fictional pharma company (Client P, 8 European markets). Not data of Viseven, of its clients or of any company.", None),
             ("Independent case study based on public data · not affiliated with or endorsed by Viseven", None),
             ("", None),
             ("How to use", B),
             ("1. KPI sheet: choose the month in the yellow cell B4. Every figure is a formula over the Data sheet.", None),
             ("2. By_market: sessions and engagement time by month; market reference from Eurostat (PUBLIC DATA).", None),
             ("3. Segments: click-through rate by HCP segment and at the same segment mix (read before ranking markets).", None),
             ("4. Compliance: contents used after their MLR expiry (alert, excluded from KPIs).", None),
             ("5. Verification: control totals against SQL (OK / CHECK) and the data checks of the load.", None),
             ("6. Definitions: how each indicator is computed (full algorithms in docs/kpi_definitions.md).", None),
             ("", None),
             ("Rules", B),
             ("· HCPs appear only as counts; groups of fewer than 5 HCPs are suppressed (blank) in Data, with secondary suppression.", None),
             ("· Brands are codes (Brand A/B/C). Activity counts only on content MLR-approved at the time of the event.", None),
             ("· Values are recalculated when the file is opened; src/check_workbook.py recomputes them and compares with SQL.", None),
             ("· Requires Excel 2021 / Microsoft 365 (XLOOKUP, LET) or LibreOffice 24.8+.", None)]
    for i, (t, f) in enumerate(lines, 1):
        ws.cell(row=i, column=1, value=t)
        if f:
            ws.cell(row=i, column=1).font = f
    ws.column_dimensions["A"].width = 130
    d = wb.create_sheet("Definitions")
    d["A1"] = "Indicator definitions (grain: month x market; full algorithms, filters and worked examples in docs/kpi_definitions.md)"
    d["A1"].font = TITLE
    header(d, 3, ["Indicator", "Formula", "Notes"])
    rows = [("HCPs targeted", "count of HCPs in Client P's target list for the market", "master data, constant over the year"),
            ("HCPs reached", "distinct HCPs with >= 1 e-detail/web session, email open or webinar join in the month", "not additive across channels"),
            ("Coverage", "HCPs reached / HCPs targeted", ""),
            ("Frequency", "(sessions + email opens + webinar joins) / HCPs reached", ""),
            ("E-detail sessions", "session_start events of the e-detail channel, sessionised per HCP and content", "sql/03_sessions.sql"),
            ("Engagement time (capped)", "start -> min(session_end, last slide_view + 30 s), minus idle gaps above 30 min between slides",
             "replaces the naive session_end duration (+38% from forgotten tabs)"),
            ("Open rate", "email_open / email_sent", "event month"),
            ("Click-through rate", "email_click / email_sent", "compare markets at the same segment mix"),
            ("Point-in-time status", "content status valid at the event time (valid_from <= ts < valid_to)", "never today's status"),
            ("Small-group rule", "cells about 1-4 HCPs are blanked, plus the smallest other segment of the same group", "")]
    for r in rows:
        d.append(list(r))
    widths(d, [26, 90, 60])


def recalc(path: Path) -> str:
    try:
        import win32com.client as w
        xl = w.DispatchEx("Excel.Application")
        xl.Visible, xl.DisplayAlerts = False, False
        wb = xl.Workbooks.Open(str(path))
        xl.CalculateFull()
        wb.Save()
        wb.Close(False)
        xl.Quit()
        return "Excel"
    except Exception as e:
        print("Excel recalculation unavailable:", type(e).__name__)
    soffice = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    if Path(soffice).exists():
        tmp = path.parent / "_lo"
        tmp.mkdir(exist_ok=True)
        subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(tmp), str(path)], check=True, timeout=180)
        shutil.move(str(tmp / path.name), str(path))
        shutil.rmtree(tmp, ignore_errors=True)
        return "LibreOffice"
    return "none (values compute on opening)"


def clean_metadata(path: Path):
    """Empty creator / lastModifiedBy / company and drop the absolute path Excel writes into workbook.xml."""
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                s = data.decode("utf-8")
                for tagname in ("dc:creator", "cp:lastModifiedBy", "dc:title", "dc:subject", "cp:keywords", "dc:description"):
                    s = re.sub(rf"<{tagname}>.*?</{tagname}>", f"<{tagname}></{tagname}>", s, flags=re.S)
                data = s.encode("utf-8")
            elif item.filename == "docProps/app.xml":
                s = data.decode("utf-8")
                for tagname in ("Company", "Manager"):
                    s = re.sub(rf"<{tagname}>.*?</{tagname}>", f"<{tagname}></{tagname}>", s, flags=re.S)
                data = s.encode("utf-8")
            elif item.filename == "xl/workbook.xml":
                s = data.decode("utf-8")
                s = re.sub(r"<mc:AlternateContent[^>]*>\s*<mc:Choice Requires=\"x15ac\">\s*<x15ac:absPath[^>]*/>\s*</mc:Choice>\s*</mc:AlternateContent>", "", s)
                s = re.sub(r"<x15ac:absPath[^>]*/>", "", s)
                data = s.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(path)


def main():
    d = q("SELECT * FROM out_report_monthly ORDER BY month, market, channel, segment")
    months = sorted(d.month.unique())
    phys = q("SELECT m.market, p.physicians, p.year, m.target_hcps AS client_p_hcps_simulated FROM dim_market m "
             "LEFT JOIN out_physicians p USING (market)")
    comp = q("SELECT * FROM out_compliance")
    k = q(f"SELECT * FROM out_kpi_market WHERE month = '{MONTH}'").set_index("market")
    tot = q("SELECT sum(sessions) s, sum(emails_sent) e FROM out_report_monthly WHERE channel='All' AND segment='All'").iloc[0]
    checks = pd.read_csv(OUT / "verification_checks.csv").query("run_label == 'after_backfill'")
    wb = Workbook()
    readme_and_defs(wb)
    n = data_sheet(wb, d)
    kpi_sheet(wb, months)
    by_market_sheet(wb, months, phys)
    segments_sheet(wb)
    compliance_sheet(wb, comp)
    q10 = '"2026-10"'
    ctl = []
    for mk in MARKETS:
        ctl.append((f"E-detail sessions {MONTH} {mk}", int(k.loc[mk, "edetail_sessions"]), f"={sif('Sessions', q10, chr(34) + mk + chr(34), 'e-detail', 'All')}"))
    for mk in MARKETS:
        ctl.append((f"HCPs reached {MONTH} {mk}", int(k.loc[mk, "hcps_reached"]), f"={sif('HCPs reached', q10, chr(34) + mk + chr(34), 'All', 'All')}"))
    ctl += [("Sessions, all months and markets", int(tot.s), '=SUMIFS(Data!$I:$I,Data!$C:$C,"All",Data!$D:$D,"All")'),
            ("Emails sent, all months and markets", int(tot.e), '=SUMIFS(Data!$L:$L,Data!$C:$C,"All",Data!$D:$D,"All")'),
            ("Rows in Data", n, "=COUNTA(Data!$A:$A)-1"),
            ("Suppressed cells in Data", int(d.suppressed.sum()), "=COUNTIFS(Data!$F:$F,TRUE)"),
            ("Sessions after MLR expiry", int(comp.sessions.sum()), f"=SUM(Compliance!$F$5:$F${4 + len(comp)})")]
    verification_sheet(wb, ctl, checks)
    wb.move_sheet("Definitions", offset=len(wb.sheetnames))
    wb.properties.creator = ""
    wb.properties.lastModifiedBy = ""
    wb.properties.title = "Client P monthly report (SIMULATED)"
    wb.save(PATH)
    how = recalc(PATH)
    clean_metadata(PATH)
    (OUT / "workbook_recalc.txt").write_text(how, encoding="utf-8")
    print("written", PATH, "| recalculated by", how, "|", n, "data rows")


if __name__ == "__main__":
    main()
