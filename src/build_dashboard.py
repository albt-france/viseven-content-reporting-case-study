"""Self-contained HTML dashboard (Plotly embedded): site/dashboard/index.html. 5 tabs, works offline.

(1) Overview · (2) Market context (PUBLIC DATA) · (3) Engagement report (SIMULATED) · (4) Data verification & loading
(SIMULATED) · (5) Incidents & compliance (SIMULATED). Every number is read from data/output or data/public.
    python src/build_dashboard.py
"""
import json

import pandas as pd
from plotly.offline import get_plotlyjs

from common import OUT, PUBLIC, ROOT

DASH = ROOT / "site" / "dashboard"
DASH.mkdir(parents=True, exist_ok=True)


def recs(name, q=None):
    d = pd.read_csv(OUT / f"{name}.csv")
    if q:
        d = d.query(q)
    return json.loads(d.to_json(orient="records"))


def data():
    npm = pd.read_csv(PUBLIC / "npm_ewizard_cli_downloads.csv", parse_dates=["day"]).set_index("day").downloads.resample("MS").sum()
    return {
        "kpi": recs("kpi_market"), "eng": recs("engagement_monthly"), "engdef": recs("engagement_definition"),
        "simpson": recs("simpson"), "std": recs("simpson_standardised"), "phys": recs("physicians"),
        "ema": recs("ema_by_year_area", "year >= 2016"), "trials": recs("trials_by_market"),
        "npm": [{"month": d.strftime("%Y-%m"), "downloads": int(v)} for d, v in npm.items()],
        "checks": recs("verification_checks"), "rec": recs("reconciliation_daily", "day >= '2026-09-08' and day <= '2026-09-20'"),
        "ro": recs("ro_hour_profile"), "bench": recs("benchmark_load"), "runs": recs("load_runs"),
        "comp": recs("compliance"), "compd": recs("compliance_weekly"), "season": recs("seasonality"), "aug": recs("august_check"),
        "pit": recs("point_in_time"), "pitr": recs("point_in_time_restatement"), "tz": recs("timezone_check"),
    }


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content-engagement reports dashboard</title>
<style>
:root { --bg:#F4F4F2; --card:#FCFCFB; --ink:#0B0B0B; --muted:#52514E; --line:#E1E0D9; --accent:#2A78D6; }
* { box-sizing:border-box; } body { margin:0; font-family:'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--ink); }
.wrap { max-width:1400px; margin:0 auto; padding:20px 16px; }
h1 { font-size:24px; margin:0 0 4px; } .sub { color:var(--muted); margin:0 0 14px; font-size:14px; }
#nav { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
#nav button { border:1px solid var(--line); background:var(--card); padding:8px 14px; border-radius:6px; cursor:pointer; font:inherit; }
#nav button.on { background:var(--accent); color:white; border-color:var(--accent); }
.tab { display:none; } .tab.on { display:block; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; } @media (max-width:900px) { .grid, .tiles { grid-template-columns:1fr !important; } }
.tiles { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; min-width:0; }
.card h2 { font-size:15px; margin:0 0 6px; } .card p { color:var(--muted); font-size:12.5px; margin:4px 0; }
.big { font-size:34px; font-weight:700; margin:4px 0; } .lab { font-size:11px; font-weight:700; color:var(--muted); letter-spacing:.05em; }
.plot { height:330px; } .wide { grid-column:1/-1; }
.tw { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:12.5px; }
th { text-align:left; color:var(--muted); border-bottom:1px solid var(--line); padding:4px 6px; font-weight:600; }
td { border-bottom:1px solid #EFEEE9; padding:4px 6px; vertical-align:top; }
.tag { font-size:10.5px; font-weight:700; padding:2px 7px; border-radius:4px; letter-spacing:.06em; margin-left:6px; white-space:nowrap; }
.pub { background:#E3EEFB; color:#1C5CAB; } .sim { background:#FBE9E0; color:#9A3B12; } .mix { background:#EDE7F6; color:#5B3E96; }
.PASS { color:#137A52; font-weight:700; } .FAIL, .ALERT { color:#B02A2A; font-weight:700; } .WARN { color:#9A6B00; font-weight:700; }
select { font:inherit; padding:4px 8px; border:1px solid var(--line); border-radius:6px; background:white; }
footer { color:#898781; font-size:12px; margin-top:16px; }
</style></head><body><div class="wrap">
<h1>Viseven: content-engagement reports that clients can trust</h1>
<p class="sub">Independent case study for the Data Analyst (Freelance) role. Real public data on the market; a fictional pharma client ("Client P", 8 markets, Dec 2025 - Nov 2026) for the report itself.</p>
<div id="nav"><button class="on" data-t="t1">Overview</button><button data-t="t2">Market context</button><button data-t="t3">Engagement report</button>
<button data-t="t4">Data verification &amp; loading</button><button data-t="t5">Incidents &amp; compliance</button></div>

<section id="t1" class="tab on">
<div class="tiles">
 <div class="card"><div class="lab">CHECKS AFTER BACKFILL <span class="tag sim">SIMULATED</span></div><div class="big" id="k1"></div><p id="k1t"></p></div>
 <div class="card"><div class="lab">EVENTS RECOVERED AFTER THE OUTAGE <span class="tag sim">SIMULATED</span></div><div class="big" id="k2"></div><p id="k2t"></p></div>
 <div class="card"><div class="lab">ENGAGEMENT TIME, CORRECTED <span class="tag sim">SIMULATED</span></div><div class="big" id="k3"></div><p id="k3t"></p></div>
 <div class="card"><div class="lab">EXPIRED CONTENT STILL IN USE <span class="tag sim">SIMULATED</span></div><div class="big" id="k4"></div><p id="k4t"></p></div>
</div>
<div class="grid">
 <div class="card"><h2>What the year's data showed, and what was done <span class="tag sim">SIMULATED</span></h2><div class="tw" id="find"></div></div>
 <div class="card"><h2>October 2026 report, by market <span class="tag sim">SIMULATED</span></h2><div class="tw" id="oct"></div>
 <p>Coverage = HCPs reached / targeted. Engagement = minutes per e-detail session, capped at the last slide + 30 s. CTR = clicks / emails sent. Groups under 5 HCPs are never shown.</p></div>
</div></section>

<section id="t2" class="tab"><div class="grid">
 <div class="card"><h2>Practising physicians by market, 2024 <span class="tag pub">PUBLIC DATA</span></h2><div id="phys" class="plot"></div><p>Eurostat hlth_rs_prs2. Ukraine is not covered. The simulated client's HCP list follows these weights.</p></div>
 <div class="card"><h2>EU human medicines still authorised, by year and area <span class="tag pub">PUBLIC DATA</span></h2><div id="ema" class="plot"></div><p>Source: European Medicines Agency. Only medicines still authorised are listed, so older years are undercounted (survivor bias). Areas grouped by keywords from MeSH terms. 2026 to 25 Nov.</p></div>
 <div class="card"><h2>Recruiting trials with a site in the market <span class="tag pub">PUBLIC DATA</span></h2><div id="tri" class="plot"></div><p>ClinicalTrials.gov API v2: paginated REST load, 1 request/s, limited fields, totalCount = rows received in every market.</p></div>
 <div class="card"><h2>Public npm downloads of ewizard-cli <span class="tag pub">PUBLIC DATA</span></h2><div id="npm" class="plot"></div><p>A public index of development activity around eWizard, as published on npm. Downloads include bots and CI: not a number of users or clients.</p></div>
</div></section>

<section id="t3" class="tab"><div class="grid">
 <div class="card wide"><h2>KPIs by market <span class="tag sim">SIMULATED</span> &nbsp; <select id="month"></select></h2><div class="tw" id="kt"></div></div>
 <div class="card"><h2>Minutes per e-detail session: naive vs capped <span class="tag sim">SIMULATED</span></h2><div id="eng" class="plot"></div><p id="engt"></p></div>
 <div class="card"><h2>Email CTR by HCP segment, DE vs PL <span class="tag sim">SIMULATED</span></h2><div id="simp" class="plot"></div><p id="simpt"></p></div>
 <div class="card wide"><h2>Coverage by market and month <span class="tag sim">SIMULATED</span></h2><div id="cov" class="plot"></div></div>
</div></section>

<section id="t4" class="tab"><div class="grid">
 <div class="card wide"><h2>Verification checks, before and after the backfill <span class="tag sim">SIMULATED</span></h2><div class="tw" id="chk"></div></div>
 <div class="card"><h2>Daily reconciliation against the source count <span class="tag sim">SIMULATED</span></h2><div id="rec" class="plot"></div><p>Check C1: distinct events per day of updated_at, warehouse vs /v1/events/count.</p></div>
 <div class="card"><h2>RO session starts by hour (UTC) <span class="tag sim">SIMULATED</span></h2><div id="ro" class="plot"></div><p id="rot"></p></div>
 <div class="card"><h2>Full vs incremental load, measured <span class="tag sim">SIMULATED</span></h2><div id="ben" class="plot"></div><p>Local API, 5 requests/s limit, client throttled to 4.5/s. Seconds measured on one laptop.</p></div>
 <div class="card"><h2>Load runs of the year <span class="tag sim">SIMULATED</span></h2><div class="tw" id="runs"></div></div>
</div></section>

<section id="t5" class="tab"><div class="grid">
 <div class="card"><h2>Outage of 14/09/2026 replayed: job v1 vs v2 <span class="tag sim">SIMULATED</span></h2><div id="inc" class="plot"></div><p>Source down 06:00-12:00 UTC. v1 moved its watermark after the failed 09:00 run; v2 moves it only after a verified batch.</p></div>
 <div class="card"><h2>Sessions per week after MLR expiry <span class="tag sim">SIMULATED</span></h2><div id="comp" class="plot"></div><div class="tw" id="compt"></div></div>
 <div class="card"><h2>August: seasonal, not a tracking failure <span class="tag mix">PUBLIC + SIMULATED</span></h2><div id="sea" class="plot"></div><p id="seat"></p></div>
 <div class="card"><h2>A current-status filter rewrites past months <span class="tag sim">SIMULATED</span></h2><div id="pit" class="plot"></div><p>March 2026 sessions as the old logic would show them on each refresh date, vs the point-in-time status.</p></div>
</div></section>
<footer>Independent case study based on public data · not affiliated with or endorsed by Viseven. Client P, its HCPs, contents and API are fictional. No medical or regulatory advice.</footer>
</div>
<script>__PLOTLY__</script>
<script>
const D = __DATA__;
const C = {blue:'#2A78D6', light:'#C9DDF5', red:'#D03B3B', grey:'#A3A19A', orange:'#EB6834', green:'#1BAF7A'};
const AREA = {'Oncology':'#2A78D6','Cardiovascular & metabolic':'#EB6834','Immunology & inflammation':'#1BAF7A','Neurology & psychiatry':'#B04FC2','Infectious diseases':'#EDA100','Rare & genetic':'#7FB3EA','Other':'#C8C6BF'};
const L = (x) => Object.assign({margin:{l:60,r:20,t:10,b:40}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{family:'Segoe UI, Arial', size:12, color:'#52514E'}, legend:{orientation:'h', y:1.12}}, x||{});
const cfg = {displayModeBar:false, responsive:true};
const pc = (v,d=1) => v==null ? '–' : (100*v).toFixed(d)+'%';
const n0 = v => v==null ? '–' : Math.round(v).toLocaleString('en');
const table = (el, cols, rows) => { document.getElementById(el).innerHTML = '<table><tr>' + cols.map(c=>'<th>'+c[0]+'</th>').join('') + '</tr>' +
  rows.map(r=>'<tr>'+cols.map(c=>'<td>'+c[1](r)+'</td>').join('')+'</tr>').join('') + '</table>'; };
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('on', x===b));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on', t.id===b.dataset.t));
  document.querySelectorAll('#'+b.dataset.t+' .js-plotly-plot').forEach(el => Plotly.Plots.resize(el));
});
// ---- overview
const after = D.checks.filter(r=>r.run_label==='after_backfill'), before = D.checks.filter(r=>r.run_label==='before_backfill');
const fails = after.filter(r=>r.status==='FAIL').length;
document.getElementById('k1').textContent = (8-fails)+' / 8';
document.getElementById('k1t').textContent = `no blocking failure (before backfill: ${before.filter(r=>r.status==='FAIL').length}); ${after.filter(r=>r.status==='WARN').length} warnings handled by documented fixes, ${after.filter(r=>r.status==='ALERT').length} compliance alert.`;
const bf = D.runs.find(r=>r.mode==='backfill'), v1 = D.runs.find(r=>r.job==='v1');
document.getElementById('k2').textContent = n0(bf.rows_inserted);
document.getElementById('k2t').textContent = `events of 14/09/2026 03:00-09:00 UTC, lost by a failed run that moved the watermark; ${n0(v1.duplicates_ignored)} duplicate rows ignored.`;
const ed = D.engdef.find(r=>r.channel==='e-detail');
document.getElementById('k3').textContent = ed.capped_min_per_session.toFixed(2)+' min';
document.getElementById('k3t').textContent = `per e-detail session, capped at the last slide + 30 s. The old figure (${ed.naive_min_per_session.toFixed(2)} min) was +${(100*ed.naive_inflation).toFixed(0)}% from ${ed.idle_sessions} forgotten tabs.`;
const ts = D.comp.reduce((a,r)=>a+r.sessions,0);
document.getElementById('k4').textContent = ts+' sessions';
document.getElementById('k4t').textContent = `on ${D.comp.length} contents (IT, Brand B), up to ${Math.max(...D.comp.map(r=>r.max_days_after_expiry))} days after MLR expiry: alert to the client, excluded from KPIs.`;
const s = k => D.simpson.find(r=>r.market===k[0]&&r.segment===k[1]);
const a26 = D.aug.find(r=>r.year===2026), a25 = D.aug.find(r=>r.year===2025);
const pr = D.pitr;
const tzr = D.tz.find(r=>r.market==='RO');
table('find', [['Situation', r=>r[0]], ['Signal', r=>r[1]], ['Action', r=>r[2]]], [
 ['Source outage 14/09', '1 failed run, C1 gap −'+n0(bf.rows_inserted)+' events', 'Backfill; watermark only after verified batch (v2)'],
 ['Duplicates after retries', n0(v1.duplicates_ignored)+' rows, same event_id', 'Idempotent insert; logged'],
 ['RO local time without offset', tzr.end_before_start_as_written+' sessions end before start', 'Read as Europe/Bucharest; 0 after fix'],
 ['DE "worse" than PL on CTR', pc(s(['DE','All']).ctr)+' vs '+pc(s(['PL','All']).ctr)+', but higher in every segment', 'Show CTR by segment and at same mix'],
 ['Idle sessions', '+'+(100*ed.naive_inflation).toFixed(0)+'% naive engagement time', 'Cap at last slide + 30 s'],
 ['Current-status filter', 'March: '+n0(pr[0].march_sessions_current_status_logic)+' → '+n0(pr[pr.length-1].march_sessions_current_status_logic)+' sessions', 'Point-in-time status'],
 ['MLR expiry', ts+' sessions after expiry', 'Compliance alert'],
 ['August −'+Math.round(-100*a26.change)+'%', 'per working day '+pc(a26.change_per_working_day)+' vs '+pc(a25.change_per_working_day)+' in 2025', '<b>Not escalated</b>: seasonal']]);
table('oct', [['Market', r=>r.market], ['Reached', r=>n0(r.hcps_reached)], ['Coverage', r=>pc(r.coverage)], ['E-detail', r=>n0(r.edetail_sessions)],
  ['Min / session', r=>r.engaged_min_per_session.toFixed(2)], ['Open rate', r=>pc(r.open_rate)], ['CTR', r=>pc(r.ctr)]], D.kpi.filter(r=>r.month==='2026-10'));
// ---- market
const ph = [...D.phys].sort((a,b)=>a.physicians-b.physicians);
Plotly.newPlot('phys', [{type:'bar', orientation:'h', y:ph.map(r=>r.market), x:ph.map(r=>r.physicians), marker:{color:C.blue},
  text:ph.map(r=>Math.round(r.physicians/1000)+'k · '+Math.round(r.per_100k)+'/100k'), textposition:'outside', cliponaxis:false,
  hovertemplate:'%{y}: %{x:,} physicians<extra></extra>'}], L({margin:{l:40,r:90,t:10,b:30}}), cfg);
const years = [...new Set(D.ema.map(r=>r.year))].sort();
Plotly.newPlot('ema', Object.keys(AREA).map(a=>({type:'bar', name:a, x:years, y:years.map(y=>(D.ema.find(r=>r.year===y&&r.area_group===a)||{medicines:0}).medicines), marker:{color:AREA[a]}})),
  L({barmode:'stack', legend:{orientation:'h', y:1.25, font:{size:10}}, margin:{l:40,r:10,t:40,b:30}}), cfg);
const tr = [...D.trials].sort((a,b)=>a.recruiting_studies-b.recruiting_studies);
Plotly.newPlot('tri', [{type:'bar', orientation:'h', name:'all areas', y:tr.map(r=>r.market), x:tr.map(r=>r.recruiting_studies), marker:{color:C.light}},
  {type:'bar', orientation:'h', name:'oncology', y:tr.map(r=>r.market), x:tr.map(r=>r.oncology), marker:{color:C.blue}}],
  L({barmode:'overlay', margin:{l:40,r:20,t:30,b:30}}), cfg);
Plotly.newPlot('npm', [{type:'bar', x:D.npm.map(r=>r.month), y:D.npm.map(r=>r.downloads), marker:{color:C.blue}}], L({margin:{l:50,r:10,t:10,b:40}}), cfg);
// ---- engagement
const months = [...new Set(D.kpi.map(r=>r.month))].sort();
const sel = document.getElementById('month');
months.forEach(m => sel.insertAdjacentHTML('beforeend', `<option ${m==='2026-10'?'selected':''}>${m}</option>`));
function kt() {
  table('kt', [['Market', r=>r.market], ['Targeted', r=>n0(r.hcps_targeted)], ['Reached', r=>n0(r.hcps_reached)], ['Coverage', r=>pc(r.coverage)],
   ['Frequency', r=>r.frequency.toFixed(2)], ['E-detail sessions', r=>n0(r.edetail_sessions)], ['Min / session (capped)', r=>r.engaged_min_per_session.toFixed(2)],
   ['Min / session (naive)', r=>r.naive_min_per_session.toFixed(2)], ['Emails sent', r=>n0(r.emails_sent)], ['Open rate', r=>pc(r.open_rate)], ['CTR', r=>pc(r.ctr)],
   ['Webinar joins', r=>n0(r.webinar_joins)]], D.kpi.filter(r=>r.month===sel.value));
}
sel.onchange = kt; kt();
Plotly.newPlot('eng', [{type:'scatter', mode:'lines+markers', name:'naive', x:D.eng.map(r=>r.month), y:D.eng.map(r=>r.naive_min), line:{color:C.red}},
  {type:'scatter', mode:'lines+markers', name:'capped', x:D.eng.map(r=>r.month), y:D.eng.map(r=>r.capped_min), line:{color:C.blue}}],
  L({yaxis:{rangemode:'tozero', title:'minutes'}}), cfg);
document.getElementById('engt').textContent = `Year: ${ed.naive_min_per_session} vs ${ed.capped_min_per_session} min per session (+${(100*ed.naive_inflation).toFixed(0)}%).`;
const segs = ['GP','Specialist','Pharmacist','All'];
Plotly.newPlot('simp', ['DE','PL'].map((m,i)=>({type:'bar', name:m, x:segs.map(x=>x==='All'?'All (as reported)':x), y:segs.map(g=>s([m,g]).ctr),
  marker:{color:i?C.orange:C.blue}, text:segs.map(g=>pc(s([m,g]).ctr)), textposition:'outside'})), L({barmode:'group', yaxis:{tickformat:'.0%'}}), cfg);
const sd = m => D.std.find(r=>r.market===m);
document.getElementById('simpt').textContent = `DE sends ${pc(s(['DE','Specialist']).share_of_sends,0)} of its emails to specialists, PL ${pc(s(['PL','Specialist']).share_of_sends,0)}. At the same segment mix: DE ${pc(sd('DE').ctr_standardised)} vs PL ${pc(sd('PL').ctr_standardised)}.`;
const mk = ['RO','PL','FR','DE','ES','IT','BG','UA'];
Plotly.newPlot('cov', [{type:'heatmap', x:months, y:mk, z:mk.map(m=>months.map(mo=>(D.kpi.find(r=>r.market===m&&r.month===mo)||{}).coverage)),
  colorscale:[[0,'#F4F4F2'],[1,'#2A78D6']], zmin:0.3, zmax:0.7, texttemplate:'%{z:.0%}', hovertemplate:'%{y} %{x}: %{z:.1%}<extra></extra>'}],
  L({margin:{l:40,r:10,t:10,b:40}}), cfg);
// ---- verification
const ids = [...new Set(D.checks.map(r=>r.check))];
table('chk', [['Check', r=>r], ['Rule', r=>after.find(x=>x.check===r).rule], ['Before backfill', r=>{const x=before.find(y=>y.check===r); return `<span class="${x.status}">${x.status}</span> ${x.observed}`;}],
  ['After backfill', r=>{const x=after.find(y=>y.check===r); return `<span class="${x.status}">${x.status}</span> ${x.observed}`;}], ['Action', r=>after.find(x=>x.check===r).action]], ids);
const rb = D.rec.filter(r=>r.run_label==='before_backfill'), ra = D.rec.filter(r=>r.run_label==='after_backfill');
Plotly.newPlot('rec', [{type:'bar', name:'source /count', x:rb.map(r=>r.day), y:rb.map(r=>r.distinct_event_ids), marker:{color:C.light}},
  {type:'bar', name:'warehouse before', x:rb.map(r=>r.day), y:rb.map(r=>r.warehouse), marker:{color:rb.map(r=>r.gap?C.red:C.blue)}},
  {type:'scatter', mode:'markers', name:'after backfill', x:ra.map(r=>r.day), y:ra.map(r=>r.warehouse), marker:{color:C.green, size:9}}],
  L({barmode:'group'}), cfg);
const vs = [['Sep 2026',C.grey,'solid'],['Oct-Nov as written',C.red,'solid'],['Oct-Nov fixed',C.blue,'dash']];
Plotly.newPlot('ro', vs.map(([v,c,d])=>{const r=D.ro.filter(x=>x.version===v), t=r.reduce((a,x)=>a+x.sessions,0);
  return {type:'scatter', mode:'lines', name:v, x:r.map(x=>x.hour_utc), y:r.map(x=>x.sessions/t), line:{color:c, dash:d}};}),
  L({yaxis:{tickformat:'.0%'}, xaxis:{title:'hour (UTC)', dtick:3}}), cfg);
document.getElementById('rot').textContent = `${tzr.naive_timestamps.toLocaleString('en')} RO timestamps without offset from 01/10/2026; ${tzr.end_before_start_as_written} sessions ended before they started as written, ${tzr.end_before_start_after_fix} after the fix.`;
const bs = D.bench.filter(r=>!r.scenario.startsWith('incident'));
Plotly.newPlot('ben', [{type:'bar', name:'requests', x:bs.map(r=>r.scenario), y:bs.map(r=>r.requests), marker:{color:C.blue},
  text:bs.map(r=>r.requests+' req · '+r.seconds+' s · '+n0(r.rows_loaded)+' rows'), textposition:'outside'}],
  L({yaxis:{type:'log', title:'requests'}}), cfg);
table('runs', [['Job', r=>r.job], ['Mode', r=>r.mode], ['Runs', r=>r.runs], ['Failed', r=>r.failed_runs], ['Requests', r=>n0(r.requests)], ['HTTP 5xx', r=>r.http_5xx],
  ['Rows inserted', r=>n0(r.rows_inserted)], ['Duplicates ignored', r=>n0(r.duplicates_ignored)]], D.runs);
// ---- incidents
const inc = D.bench.filter(r=>r.scenario.startsWith('incident'));
Plotly.newPlot('inc', [{type:'bar', x:inc.map(r=>r.scenario==='incident_v1'?'v1: watermark after failure':'v2: watermark after verified batch'), y:inc.map(r=>r.lost_events),
  marker:{color:inc.map(r=>r.lost_events?C.red:C.green)}, text:inc.map(r=>r.lost_events+' events lost'), textposition:'outside'}], L({yaxis:{rangemode:'tozero'}}), cfg);
Plotly.newPlot('comp', [...new Set(D.compd.map(r=>r.content_id))].map((c,i)=>({type:'bar', name:c, x:D.compd.filter(r=>r.content_id===c).map(r=>'week of '+r.week),
  y:D.compd.filter(r=>r.content_id===c).map(r=>r.sessions), marker:{color:i?C.orange:C.red}})), L({barmode:'group', margin:{l:40,r:10,t:30,b:40}}), cfg);
table('compt', [['Content', r=>r.content_id], ['Market', r=>r.market], ['Brand', r=>r.brand], ['MLR expiry', r=>r.mlr_expiry], ['Sessions', r=>r.sessions], ['HCPs', r=>r.hcps], ['Days after', r=>r.max_days_after_expiry]], D.comp);
['prior-year report','event data'].forEach(()=>{});
Plotly.newPlot('sea', ['prior-year report','event data'].map((src,i)=>({type:'scatter', mode:'lines+markers', name:src, x:D.season.filter(r=>r.source===src).map(r=>r.month),
  y:D.season.filter(r=>r.source===src).map(r=>r.sessions_per_market_working_day), line:{color:i?C.blue:C.grey}})), L({yaxis:{rangemode:'tozero', title:'sessions per market working day'}}), cfg);
document.getElementById('seat').textContent = `July -> August: ${pc(a26.change)} in 2026 and ${pc(a25.change)} in 2025; per working day ${pc(a26.change_per_working_day)} vs ${pc(a25.change_per_working_day)}. Holidays: Nager.Date.`;
Plotly.newPlot('pit', [{type:'bar', name:'old: current status', x:pr.map(r=>r.published_on), y:pr.map(r=>r.march_sessions_current_status_logic), marker:{color:C.light},
  text:pr.map(r=>n0(r.march_sessions_current_status_logic)), textposition:'outside'},
  {type:'scatter', mode:'lines', name:'point-in-time', x:pr.map(r=>r.published_on), y:pr.map(r=>r.march_sessions_point_in_time), line:{color:C.blue, dash:'dash'}}],
  L({yaxis:{rangemode:'tozero'}}), cfg);
</script></body></html>"""


def main():
    html = HTML.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", json.dumps(data(), ensure_ascii=False))
    out = DASH / "index.html"
    out.write_text(html, encoding="utf-8")
    print("written", out, f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
