"""CSS / HTML / JS for the market-trend panel and the per-stock signal timeline.

Kept as plain (non-f-string) strings so the JS can use braces freely; report.py splices them in.
Charts are hand-built SVG: 2px lines, recessive grid, a crosshair + tooltip on hover, direct
labels at the line ends, and a "看數字" table for every chart.
"""

TREND_CSS = """
.trend { background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px 12px; margin-bottom: 18px; box-shadow: var(--shadow); }
.trend[hidden] { display: none; }
.trend-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.trend-head h2 { font-family: "Source Serif 4", Georgia, serif; font-size: 18px; font-weight: 600; margin: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chips button { font-family: inherit; font-size: 12.5px; padding: 5px 11px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--paper); color: var(--ink-soft); cursor: pointer; }
.chips button:hover { border-color: var(--accent); }
.chips button.active { background: var(--accent); border-color: var(--accent); color: var(--paper); }
.chips button:focus-visible, .trend summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart .ax { fill: var(--ink-faint); font: 11px "IBM Plex Mono", monospace; }
.chart .gl { stroke: var(--line); stroke-width: 1; }
.chart .xh { stroke: var(--ink-faint); stroke-width: 1; stroke-dasharray: 3 3; }
.chart .end-label { font: 600 12px "IBM Plex Sans", "PingFang TC", sans-serif; }
.chart .tip { position: absolute; top: 6px; z-index: 2; background: var(--paper); border: 1px solid var(--line-strong); border-radius: 8px; padding: 8px 10px; font-size: 12px; line-height: 1.6; box-shadow: var(--shadow); pointer-events: none; white-space: nowrap; }
.chart .tip b { font-family: "IBM Plex Mono", monospace; font-weight: 500; }
.chart .tip .sw { display: inline-block; width: 10px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
.key-row { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 6px 0 2px; font-size: 12px; color: var(--ink-soft); }
.key-row span { display: inline-flex; align-items: center; gap: 6px; }
.key-row .sw { width: 16px; height: 0; border-top: 2px solid; }
.key-row .dot { width: 9px; height: 9px; border-radius: 50%; }
.trend-note { font-size: 12px; color: var(--ink-faint); margin: 6px 0 0; }
.trend details { margin-top: 8px; font-size: 12.5px; color: var(--ink-soft); }
.trend summary { cursor: pointer; width: fit-content; }
.num-table { overflow-x: auto; margin-top: 6px; max-height: 260px; overflow-y: auto; border: 1px solid var(--line); border-radius: 8px; }
.num-table table { min-width: 0; font-size: 12.5px; }
.num-table th, .num-table td { padding: 5px 12px; text-align: right; white-space: nowrap; font-family: "IBM Plex Mono", monospace; }
.num-table th:first-child, .num-table td:first-child { text-align: left; }
.history { margin-top: 12px; border-top: 1px solid var(--line); padding-top: 12px; }
.history h3 { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--ink-soft); }
.hist-row { display: flex; gap: 10px; align-items: baseline; padding: 3px 0; }
.hist-row .hd { font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--ink-faint); flex: 0 0 46px; }
.hist-row .hb { min-width: 0; }
.hist-empty { font-size: 12.5px; color: var(--ink-faint); margin: 0; }
.sc-box { margin: 4px 0 14px; }
.sc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px 12px; flex-wrap: wrap; margin-bottom: 6px; }
.sc-price { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sc-price b { font-family: "IBM Plex Mono", monospace; font-size: 22px; font-weight: 500; }
.sc-chg { font-family: "IBM Plex Mono", monospace; font-size: 13px; font-weight: 500; }
.sc-box .chart { touch-action: pan-y; cursor: grab; user-select: none; -webkit-user-select: none; }
.sc-box .chart:active { cursor: grabbing; }
.chart { -webkit-tap-highlight-color: transparent; }
.sc-ctrl .chips button.zb { min-width: 34px; font-family: "IBM Plex Mono", monospace; }
.sc-ctrl .chips button:disabled { opacity: .4; cursor: default; }
.sc-hint { font-size: 11.5px; color: var(--ink-faint); margin: 2px 0 0; }
.sc-ctrl { display: flex; gap: 6px 10px; flex-wrap: wrap; }
.sc-ctrl .chips button.opt { border-style: dashed; }
.sc-ctrl .chips button.opt.active { border-style: solid; }
.chart .sc-ovl { font: 500 11px "IBM Plex Sans", "PingFang TC", sans-serif; fill: var(--ink-soft); paint-order: stroke; stroke: var(--paper); stroke-width: 3px; }
.sc-note { font-size: 12px; color: var(--ink-faint); margin: 4px 0 0; }
.key-row .cdl { width: 8px; height: 12px; border: 1px solid; border-radius: 1px; background: var(--paper); }
"""

TREND_HTML = """
  <section id="trend" class="trend" aria-label="市場趨勢">
    <div class="trend-head">
      <h2>市場趨勢</h2>
      <div id="trend-range" class="chips" role="group" aria-label="時間範圍"></div>
    </div>
    <div id="trend-tabs" class="chips" role="group" aria-label="指標" style="margin-bottom:10px"></div>
    <div id="trend-chart"></div>
    <div id="trend-key" class="key-row"></div>
    <p id="trend-note" class="trend-note"></p>
    <details>
      <summary>看數字</summary>
      <div id="trend-tbl" class="num-table"></div>
    </details>
  </section>
"""

# Expects globals: HIST {codes, days:[{d,n,s:{sid:[idx]}}]}, SER {dates, v:{sid:{c,m}}},
# TREND_METRICS [{key,label,weekly?,zero?,note?,series:[{name,codes,color,dash?}]}],
# SIGLABEL {code: text}, BULL_CODES / BEAR_CODES (arrays), plus the page's badgeStyle/codeCategory.
TREND_JS = r"""
const CHART_REG = {};
let chartSeq = 0;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const mdLabel = d => d.slice(5).replace('-', '/');

function chartWidth() {
  return Math.max(280, Math.min(840, document.documentElement.clientWidth - 28 - 38));
}

function niceAxis(minV, maxV, zero) {
  if (zero) minV = 0;
  if (maxV <= minV) maxV = minV + 1;
  const raw = (maxV - minV) / 4;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  const lo = zero ? 0 : Math.floor(minV / step) * step;
  const hi = Math.ceil(maxV / step) * step;
  const ticks = [];
  for (let t = lo; t <= hi + step / 2; t += step) ticks.push(+t.toFixed(6));
  return { lo, hi, ticks };
}

// spec: {xs:[label], series:[{name,color(css var),dash,vals}], zero, h, endLabels, tip(i)->html, markers:[{i,color,y}]}
function drawChart(spec) {
  const id = 'ch' + (++chartSeq);
  const W = chartWidth(), H = spec.h || 220;
  const padL = 44, padR = spec.endLabels ? 52 : 14, padT = 12, padB = 24;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const n = spec.xs.length;
  const all = spec.series.flatMap(s => s.vals).filter(v => v !== null && v !== undefined);
  if (!all.length) return '<p class="hist-empty">資料不足,畫不出走勢。</p>';
  const ax = niceAxis(Math.min(...all), Math.max(...all), spec.zero);
  const X = i => padL + (n === 1 ? plotW / 2 : i * plotW / (n - 1));
  const Y = v => padT + plotH - (v - ax.lo) / (ax.hi - ax.lo) * plotH;
  CHART_REG[id] = { spec, W, padL, plotW, n, X };

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(spec.label || '趨勢圖')}">`;
  ax.ticks.forEach(t => {
    const y = Y(t).toFixed(1);
    svg += `<line class="gl" x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}"/><text class="ax" x="${padL - 8}" y="${+y + 4}" text-anchor="end">${spec.yFmt ? spec.yFmt(t) : t}</text>`;
  });
  const xt = Math.min(n, W < 420 ? 4 : 6);
  for (let k = 0; k < xt; k++) {
    const i = xt === 1 ? 0 : Math.round(k * (n - 1) / (xt - 1));
    svg += `<text class="ax" x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="${k === 0 ? 'start' : k === xt - 1 ? 'end' : 'middle'}">${spec.xs[i]}</text>`;
  }
  spec.series.forEach(s => {
    let d = '', pen = false;
    s.vals.forEach((v, i) => {
      if (v === null || v === undefined) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`;
      pen = true;
    });
    svg += `<path d="${d}" fill="none" style="stroke:var(${s.color})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
    let last = s.vals.length - 1;
    while (last >= 0 && (s.vals[last] === null || s.vals[last] === undefined)) last--;
    if (last >= 0) {
      svg += `<circle cx="${X(last).toFixed(1)}" cy="${Y(s.vals[last]).toFixed(1)}" r="4" style="fill:var(${s.color});stroke:var(--paper)" stroke-width="2"/>`;
      if (spec.endLabels) {
        svg += `<text class="end-label" x="${(X(last) + 9).toFixed(1)}" y="${(Y(s.vals[last]) + 4).toFixed(1)}" style="fill:var(--ink)">${esc(s.name)}</text>`;
      }
    }
  });
  (spec.markers || []).forEach(m => {
    svg += `<circle cx="${X(m.i).toFixed(1)}" cy="${Y(m.y).toFixed(1)}" r="4.5" style="fill:var(${m.color});stroke:var(--paper)" stroke-width="2"/>`;
  });
  svg += `<line class="xh" y1="${padT}" y2="${padT + plotH}" x1="0" x2="0" visibility="hidden"/></svg>`;
  return `<div class="chart" data-id="${id}">${svg}<div class="tip" hidden></div></div>`;
}

function hideTips(except) {
  document.querySelectorAll('.chart').forEach(c => {
    if (c === except) return;
    c.querySelector('.tip').hidden = true;
    c.querySelector('.xh').setAttribute('visibility', 'hidden');
  });
}

// Charts show nothing on hover: tap / click a day to pin its crosshair and numbers, tap it again (or
// anywhere off the chart) to clear. On the per-stock chart a horizontal drag pans, two fingers or
// Ctrl/⌘ + wheel (trackpad pinch) zoom; a press only counts as a tap if it barely moved.
let scSel = null;  // {sid, date}: the day picked on a stock chart, kept across zoom / pan redraws

function showTip(wrap, i) {
  const reg = CHART_REG[wrap.dataset.id];
  if (!reg) return;
  i = Math.max(0, Math.min(reg.n - 1, i));
  hideTips(wrap);
  const svg = wrap.querySelector('svg');
  const rect = svg.getBoundingClientRect();
  const x = reg.X(i);
  const xh = wrap.querySelector('.xh');
  xh.setAttribute('x1', x); xh.setAttribute('x2', x); xh.setAttribute('visibility', 'visible');
  const tip = wrap.querySelector('.tip');
  tip.innerHTML = reg.spec.tip(i);
  tip.hidden = false;
  wrap.dataset.sel = i;
  const scale = rect.width / reg.W;
  const tw = tip.offsetWidth;
  let left = x * scale + 12;
  if (left + tw > rect.width) left = x * scale - tw - 12;
  tip.style.left = Math.max(0, left) + 'px';
}

function clearTip(wrap) {
  wrap.querySelector('.tip').hidden = true;
  wrap.querySelector('.xh').setAttribute('visibility', 'hidden');
  delete wrap.dataset.sel;
}

function tapChart(wrap, clientX) {
  const reg = CHART_REG[wrap.dataset.id];
  if (!reg) return;
  const rect = wrap.querySelector('svg').getBoundingClientRect();
  const px = (clientX - rect.left) * (reg.W / rect.width);
  let i = reg.idx ? reg.idx(px) : Math.round((px - reg.padL) / reg.plotW * (reg.n - 1));
  i = Math.max(0, Math.min(reg.n - 1, i));
  const box = wrap.closest('.sc-box');
  if (!wrap.querySelector('.tip').hidden && +wrap.dataset.sel === i) {
    clearTip(wrap);
    if (box) scSel = null;
    return;
  }
  showTip(wrap, i);
  if (box && reg.dates) scSel = { sid: box.dataset.sid, date: reg.dates[i] };
}

let press = null;  // the press in progress on a chart
document.addEventListener('pointerdown', e => {
  const wrap = e.target.closest && e.target.closest('.chart');
  if (!wrap) {
    if (!(e.target.closest && e.target.closest('.sc-ctrl'))) { hideTips(null); scSel = null; }
    return;
  }
  const box = wrap.closest('.sc-box');
  if (!press || press.wrap !== wrap) press = { wrap, box, pts: new Map(), moved: false, pinched: false };
  press.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (press.pts.size === 1) Object.assign(press, { x0: e.clientX, y0: e.clientY, end0: scEnd });
  if (box && press.pts.size === 2) {
    const [p1, p2] = [...press.pts.values()];
    press.pinch = { d0: Math.max(10, Math.abs(p1.x - p2.x)), span0: scSpan(), end0: scEnd, mid: (p1.x + p2.x) / 2 };
    press.pinched = true;
  }
});
document.addEventListener('pointermove', e => {
  if (!press || !press.pts.has(e.pointerId)) return;
  press.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (!press.box) return;
  const svg = press.box.querySelector('.chart svg');
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  if (press.pinch && press.pts.size >= 2) {
    const [p1, p2] = [...press.pts.values()];
    const d = Math.max(10, Math.abs(p1.x - p2.x));
    zoomTo(press.pinch.span0 * press.pinch.d0 / d, (press.pinch.mid - rect.left) / rect.width, press.pinch.span0, press.pinch.end0);
    return;
  }
  if (press.pinched) return;
  const dx = e.clientX - press.x0;
  if (!press.moved && Math.abs(dx) < 6) return;
  press.moved = true;
  const barPx = rect.width / scSpan();
  setView(scSpan(), press.end0 + Math.round(dx / barPx));
});
function endPress(e, cancelled) {
  if (!press || !press.pts.has(e.pointerId)) return;
  press.pts.delete(e.pointerId);
  if (press.pts.size) return;
  const moved = press.moved || press.pinched || Math.abs(e.clientY - press.y0) > 8 || Math.abs(e.clientX - press.x0) > 6;
  if (!cancelled && !moved) tapChart(press.wrap.isConnected ? press.wrap : press.box.querySelector('.chart'), e.clientX);
  press = null;
}
document.addEventListener('pointerup', e => endPress(e, false));
document.addEventListener('pointercancel', e => endPress(e, true));
document.addEventListener('wheel', e => {
  if (!(e.ctrlKey || e.metaKey)) return;
  const box = e.target.closest && e.target.closest('.sc-box');
  if (!box || !e.target.closest('.chart')) return;
  e.preventDefault();
  const rect = box.querySelector('.chart svg').getBoundingClientRect();
  zoomTo(scSpan() * Math.exp(e.deltaY * 0.01), (e.clientX - rect.left) / rect.width, scSpan(), scEnd);
}, { passive: false });

// ---------------- market trend ----------------
const TREND_RANGES = [['30', '近30日', 30], ['60', '近60日', 60], ['all', '全部', 9999]];
let trendMetric = 'all', trendRange = '60';

function isoMonday(d) {
  const t = new Date(d + 'T00:00:00Z');
  t.setUTCDate(t.getUTCDate() - ((t.getUTCDay() + 6) % 7));
  return t.toISOString().slice(0, 10);
}

function trendData(metric) {
  const idx = {};
  HIST.codes.forEach((c, i) => { idx[c] = i; });
  const days = HIST.days.slice(-(TREND_RANGES.find(r => r[0] === trendRange)[2]));
  const perDay = days.map(day => {
    const counts = metric.series.map(ser => {
      const set = ser.codes === '*' ? null : new Set(ser.codes.map(c => idx[c]).filter(v => v !== undefined));
      let c = 0;
      for (const sid in day.s) { if (set === null || day.s[sid].some(v => set.has(v))) c++; }
      return c;
    });
    return { d: day.d, n: day.n, counts };
  });
  if (!metric.weekly) return perDay.map(r => ({ label: mdLabel(r.d), full: r.d, n: r.n, counts: r.counts }));
  const weeks = [];
  perDay.forEach(r => {
    const key = isoMonday(r.d);
    let w = weeks.find(x => x.key === key);
    if (!w) { w = { key, counts: metric.series.map(() => 0), n: r.n }; weeks.push(w); }
    r.counts.forEach((c, i) => { w.counts[i] += c; });
    w.n = r.n;
  });
  return weeks.map(w => ({ label: mdLabel(w.key), full: '當週(' + mdLabel(w.key) + ' 起)', n: w.n, counts: w.counts }));
}

function renderTrend() {
  const sec = document.getElementById('trend');
  if (!sec) return;
  const chartEl = document.getElementById('trend-chart');
  if (!HIST.days || HIST.days.length < 2) {
    chartEl.innerHTML = '<p class="hist-empty">歷史紀錄累積中,至少要有兩個交易日才畫得出趨勢。</p>';
    ['trend-key', 'trend-tbl', 'trend-tabs', 'trend-range'].forEach(id => { document.getElementById(id).innerHTML = ''; });
    document.getElementById('trend-note').textContent = '';
    return;
  }
  const tabs = document.getElementById('trend-tabs');
  tabs.innerHTML = '';
  TREND_METRICS.forEach(m => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = m.label;
    b.className = m.key === trendMetric ? 'active' : '';
    b.setAttribute('aria-pressed', m.key === trendMetric);
    b.addEventListener('click', () => { trendMetric = m.key; renderTrend(); });
    tabs.appendChild(b);
  });
  const rng = document.getElementById('trend-range');
  rng.innerHTML = '';
  TREND_RANGES.forEach(([key, label]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
    b.className = key === trendRange ? 'active' : '';
    b.setAttribute('aria-pressed', key === trendRange);
    b.addEventListener('click', () => { trendRange = key; renderTrend(); });
    rng.appendChild(b);
  });

  const metric = TREND_METRICS.find(m => m.key === trendMetric);
  const rows = trendData(metric);
  const spec = {
    label: metric.label, xs: rows.map(r => r.label), zero: true, h: 220, endLabels: metric.series.length > 1,
    series: metric.series.map((s, i) => ({ name: s.name, color: s.color, dash: s.dash, vals: rows.map(r => r.counts[i]) })),
    tip: i => {
      const r = rows[i];
      const lines = metric.series.map((s, k) =>
        `<div><i class="sw" style="background:var(${s.color})"></i>${esc(s.name)} <b>${r.counts[k]}</b> 檔</div>`).join('');
      return `<div><b>${esc(r.full)}</b></div>${lines}<div style="color:var(--ink-faint)">當日評估 ${r.n} 檔</div>`;
    },
  };
  chartEl.innerHTML = drawChart(spec);
  document.getElementById('trend-key').innerHTML = metric.series.length > 1
    ? metric.series.map(s => `<span><i class="sw" style="border-color:var(${s.color});${s.dash ? 'border-top-style:dashed' : ''}"></i>${esc(s.name)}</span>`).join('')
    : '';
  document.getElementById('trend-note').textContent = metric.note || '';
  const head = '<tr><th>' + (metric.weekly ? '週' : '日期') + '</th>' + metric.series.map(s => `<th>${esc(s.name)}</th>`).join('') + '<th>評估檔數</th></tr>';
  const body = rows.slice().reverse().map(r =>
    `<tr><td>${esc(metric.weekly ? r.label + ' 起' : r.full)}</td>${r.counts.map(c => `<td>${c}</td>`).join('')}<td>${r.n}</td></tr>`).join('');
  document.getElementById('trend-tbl').innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

// ---------------- per-stock timeline ----------------
function stockSignalsByDate(sid) {
  const out = {};
  HIST.days.forEach(day => {
    const idxs = day.s[sid];
    if (idxs && idxs.length) out[day.d] = idxs.map(i => HIST.codes[i]);
  });
  return out;
}

function markerColor(codes) {
  const bull = codes.some(c => BULL_CODES.includes(c));
  const bear = codes.some(c => BEAR_CODES.includes(c));
  if (bull && !bear) return '--rise';
  if (bear && !bull) return '--fall';
  return '--warn';
}

// Core signals marked on the candles (the backtest found these carry information; crossovers and
// 5/20-day line crossings are left to the tooltip and the list below so the chart stays readable).
const MARK_UP = new Set(["new_high", "w_new_high", "rsi_overbought", "w_rsi_overbought", "bb_breakout_upper", "w_bb_breakout_upper"]);
const MARK_DN = new Set(["new_low", "w_new_low", "rsi_oversold", "w_rsi_oversold", "bb_breakout_lower", "w_bb_breakout_lower"]);
const MARK_VOL = new Set(["volume_spike", "w_volume_spike"]);
const SC_RANGES = [[20, '1個月'], [60, '3個月'], [120, '6個月']];
let scRange = 60;
try { scRange = +localStorage.getItem('sc-range') || 60; } catch (e) {}
if (!SC_RANGES.some(r => r[0] === scRange)) scRange = 60;
let scEnd = 0;           // bars between the right edge of the view and the latest bar (0 = today)
const SC_MIN_SPAN = 10;  // zoom-in limit
const scTotal = () => SER.dates.length;
const scSpan = () => Math.max(Math.min(SC_MIN_SPAN, scTotal()), Math.min(scRange, scTotal()));

function setView(span, end) {
  const total = scTotal();
  span = Math.round(Math.max(Math.min(SC_MIN_SPAN, total), Math.min(total, span)));
  end = Math.round(Math.max(0, Math.min(total - span, end)));
  if (span === scSpan() && end === scEnd) return;
  scRange = span; scEnd = end;
  redrawStockCharts();
}

// Zoom around a point: `frac` is where the pointer sits across the chart (0 = left, 1 = right); the
// bar under it stays put. span0 / end0 are the view the gesture started from.
function zoomTo(span, frac, span0, end0) {
  const total = scTotal();
  frac = Math.max(0, Math.min(1, frac));
  span = Math.max(Math.min(SC_MIN_SPAN, total), Math.min(total, Math.round(span)));
  const to0 = total - end0, from0 = to0 - span0;
  const anchor = from0 + frac * span0;
  const to = anchor - frac * span + span;
  setView(span, total - to);
}

let scRedraw = 0;
function redrawStockCharts() {
  if (scRedraw) return;
  scRedraw = requestAnimationFrame(() => {
    scRedraw = 0;
    document.querySelectorAll('.sc-box').forEach(box => {
      const stock = STOCKS.find(s => s.stock_id === box.dataset.sid);
      if (!stock) return;
      box.innerHTML = candleChart(stock, SER.v[stock.stock_id], stockSignalsByDate(stock.stock_id));
      if (scSel && scSel.sid === stock.stock_id) {
        const wrap = box.querySelector('.chart');
        const reg = wrap && CHART_REG[wrap.dataset.id];
        const i = reg && reg.dates ? reg.dates.indexOf(scSel.date) : -1;
        if (i >= 0) showTip(wrap, i);
      }
    });
  });
}
// Overlay toggles: 切線 (A) and 支撐壓力 (C), off by default, remembered per browser.
const scOpt = { tl: false, sr: false };
try { Object.assign(scOpt, JSON.parse(localStorage.getItem('sc-opt') || '{}')); } catch (e) {}

// Swing points: a bar whose high (low) is the highest (lowest) of the k bars on each side.
// Needs k later bars to confirm, so the newest k bars can't be a swing point yet.
function swings(vals, k, isHigh) {
  const out = [];
  for (let i = k; i < vals.length - k; i++) {
    const v = vals[i];
    if (v === null || v === undefined) continue;
    let ok = true;
    for (let j = i - k; j <= i + k && ok; j++) {
      if (j === i || vals[j] === null || vals[j] === undefined) continue;
      if (isHigh ? vals[j] > v : vals[j] < v) ok = false;
    }
    if (ok) out.push(i);
  }
  return out;
}

// A: trend lines, textbook definition: a falling resistance joins two lower swing highs (下降趨勢線),
// a rising support joins two higher swing lows (上升趨勢線). Newest pair first.
// A line counts only if no close after its first point broke through it (0.5% tolerance), so what is
// drawn is a line the price still respects today.
function trendLine(vals, closes, isHigh) {
  const piv = swings(vals, 5, isHigh);
  const last = closes.length - 1;
  for (let b = piv.length - 1; b >= 1; b--) {
    for (let a = b - 1; a >= 0; a--) {
      const i1 = piv[a], i2 = piv[b];
      if (i2 - i1 < 8) continue;
      if (isHigh ? vals[i2] >= vals[i1] : vals[i2] <= vals[i1]) continue;
      const slope = (vals[i2] - vals[i1]) / (i2 - i1);
      const at = i => vals[i1] + slope * (i - i1);
      let ok = at(last) > 0, touches = 0;
      for (let i = i1; i <= last && ok; i++) {
        const cl = closes[i];
        if (cl === null || cl === undefined) continue;
        if (isHigh ? cl > at(i) * 1.005 : cl < at(i) * 0.995) ok = false;
        if (vals[i] !== null && vals[i] !== undefined && Math.abs(vals[i] / at(i) - 1) < 0.01) touches++;
      }
      if (ok) return { i1, i2, slope, at, touches };
    }
  }
  return null;
}

// C: horizontal levels. Swing highs and lows within ~1.5% of each other form one level; a level
// needs at least two touches. Shown: the nearest one under the last close and the nearest above.
function srLevels(h, l, c) {
  const pts = [...swings(h, 3, true).map(i => h[i]), ...swings(l, 3, false).map(i => l[i])].sort((a, b) => a - b);
  const groups = [];
  pts.forEach(p => {
    const g = groups[groups.length - 1];
    if (g && p <= g.lo * 1.015) { g.pts.push(p); g.hi = p; } else groups.push({ lo: p, hi: p, pts: [p] });
  });
  let li = c.length - 1;
  while (li >= 0 && (c[li] === null || c[li] === undefined)) li--;
  if (li < 0) return {};
  const px = c[li];
  const lv = groups.filter(g => g.pts.length >= 2)
    .map(g => ({ level: g.pts.reduce((x, y) => x + y, 0) / g.pts.length, lo: g.lo, hi: g.hi, n: g.pts.length }));
  const below = lv.filter(g => g.level < px).sort((a, b) => b.level - a.level)[0] || null;
  const above = lv.filter(g => g.level > px).sort((a, b) => a.level - b.level)[0] || null;
  return { support: below, resist: above };
}

const SC_OVERLAY = {};
function overlays(sid, ser) {
  if (!SC_OVERLAY[sid]) {
    const h = ser.h.map((x, i) => x ?? ser.c[i]), l = ser.l.map((x, i) => x ?? ser.c[i]);
    SC_OVERLAY[sid] = {
      res: trendLine(h, ser.c, true), sup: trendLine(l, ser.c, false), lv: srLevels(h, l, ser.c),
    };
  }
  return SC_OVERLAY[sid];
}

const nfmt = v => v === null || v === undefined ? '—' : (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-US') : String(+(+v).toFixed(2)));
const vfmt = v => {
  if (v === null || v === undefined) return '—';
  const a = Math.abs(v);
  if (VOL_UNIT.includes('張')) return a >= 1e8 ? (v / 1e8).toFixed(1) + '億' : a >= 1e4 ? (v / 1e4).toFixed(1) + '萬' : nfmt(v);
  return a >= 1e9 ? (v / 1e9).toFixed(1) + 'B' : a >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : a >= 1e4 ? (v / 1e3).toFixed(0) + 'K' : nfmt(v);
};

function candleChart(stock, ser, byDate) {
  const id = 'ch' + (++chartSeq);
  const total = SER.dates.length;
  const span = scSpan();
  const to = total - Math.max(0, Math.min(total - span, scEnd));  // exclusive right edge of the view
  const from = to - span;
  const dates = SER.dates.slice(from, to);
  const cut = k => (ser[k] || []).slice(from, to);
  const o = cut('o'), h = cut('h'), l = cut('l'), c = cut('c'), v = cut('v'), m = cut('m'), q = cut('q');
  const prevC = from > 0 ? ser.c[from - 1] : null;
  const n = dates.length;
  const W = chartWidth();
  const narrow = W < 420;
  const padL = 8, padR = (scOpt.tl || scOpt.sr) ? 62 : 52, padT = 14;
  const priceH = narrow ? 210 : 250, gap = 10, volH = narrow ? 46 : 56, padB = 22;
  const H = padT + priceH + gap + volH + padB;
  const plotW = W - padL - padR;
  const slot = plotW / n;
  const X = i => padL + (i + 0.5) * slot;
  const hi = h.map((x, i) => x ?? c[i]), lo = l.map((x, i) => x ?? c[i]);
  const ov = overlays(stock.stock_id, ser);
  const tags = [];  // value tags in the right gutter, spread apart after everything is placed
  const tlines = scOpt.tl ? [['res', ov.res], ['sup', ov.sup]].filter(t => t[1]) : [];
  const levels = scOpt.sr ? [['resist', ov.lv.resist], ['support', ov.lv.support]].filter(t => t[1]) : [];
  const extra = [];
  tlines.forEach(([, t]) => { extra.push(t.at(Math.max(from, t.i1)), t.at(to - 1)); });
  levels.forEach(([, g]) => extra.push(g.lo, g.hi));
  const pv = [...hi, ...lo, ...m, ...q, ...extra].filter(x => x !== null && x !== undefined);
  if (!pv.length) return '<p class="hist-empty">資料不足,畫不出走勢。</p>';
  // Fit the price panel to the data (small margin) instead of rounding out to whole ticks,
  // so the candles use the full height; gridlines are the nice ticks that fall inside.
  let pMin = Math.min(...pv), pMax = Math.max(...pv);
  if (pMax <= pMin) { pMax = pMin * 1.01 + 0.01; pMin = pMin * 0.99; }
  const padV = (pMax - pMin) * 0.06;
  const ax = { lo: pMin - padV, hi: pMax + padV };
  {
    const raw = (ax.hi - ax.lo) / 5, pw = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / pw;
    const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * pw;
    ax.ticks = [];
    for (let t = Math.ceil(ax.lo / step) * step; t <= ax.hi; t += step) ax.ticks.push(+t.toFixed(6));
  }
  const Y = val => padT + priceH - (val - ax.lo) / (ax.hi - ax.lo) * priceH;
  let lastIdx = n - 1;
  while (lastIdx >= 0 && (c[lastIdx] === null || c[lastIdx] === undefined)) lastIdx--;
  const tagY = lastIdx >= 0 ? Y(c[lastIdx]) : -1e9;
  const tagYs = [];  // filled below once overlays are known; ticks are drawn first, so precompute
  if (scOpt.sr) [ov.lv.resist, ov.lv.support].forEach(g => g && tagYs.push(Y(g.level)));
  if (scOpt.tl) [ov.res, ov.sup].forEach(t => t && tagYs.push(Y(t.at(to - 1))));
  const vmax = Math.max(1, ...v.filter(x => x !== null && x !== undefined));
  const vTop = padT + priceH + gap;
  const VY = val => vTop + volH - (val / vmax) * volH;
  const bw = Math.max(1, Math.min(14, slot * 0.64));

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(stock.name)} K線、成交量與均線">`;
  // grid + right-side price axis
  ax.ticks.forEach(t => {
    const y = Y(t).toFixed(1);
    svg += `<line class="gl" x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}"/>`;
    if (Math.abs(+y - tagY) > 13 && !tagYs.some(ty => Math.abs(+y - ty) < 13)) svg += `<text class="ax" x="${W - padR + 6}" y="${+y + 4}">${nfmt(t)}</text>`;
  });
  svg += `<line class="gl" x1="${padL}" x2="${W - padR}" y1="${vTop + volH}" y2="${vTop + volH}"/>`;
  svg += `<text class="ax" x="${W - padR + 6}" y="${vTop + 9}">${vfmt(vmax)}</text>`;
  // month ticks on the x axis
  let lastMonth = '';
  const minGap = narrow ? 52 : 64;
  let lastX = padL + 12;  // keep month labels clear of the start-date label at the left edge
  dates.forEach((d, i) => {
    const mo = d.slice(0, 7);
    if (mo !== lastMonth) {
      lastMonth = mo;
      if (i > 0 && X(i) - lastX >= minGap && X(i) < W - padR - 16) {
        svg += `<line class="gl" x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="${padT}" y2="${vTop + volH}" stroke-dasharray="2 4"/>`;
        svg += `<text class="ax" x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="middle">${+d.slice(5, 7)}月</text>`;
        lastX = X(i);
      }
    }
  });
  svg += `<text class="ax" x="${padL}" y="${H - 6}">${mdLabel(dates[0])}</text>`;
  // volume bars
  dates.forEach((d, i) => {
    if (v[i] === null || v[i] === undefined) return;
    const up = c[i] !== null && o[i] !== null ? c[i] >= o[i] : true;
    const spike = (byDate[d] || []).some(x => MARK_VOL.has(x));
    const col = spike ? '--vol' : up ? '--rise' : '--fall';
    const y = VY(v[i]);
    svg += `<rect x="${(X(i) - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.5, vTop + volH - y).toFixed(1)}" style="fill:var(${col})" opacity="${spike ? 1 : 0.45}"/>`;
  });
  // moving averages
  [[q, '--info'], [m, '--warn']].forEach(([vals, col]) => {
    let d = '', pen = false;
    vals.forEach((val, i) => {
      if (val === null || val === undefined) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(val).toFixed(1)}`;
      pen = true;
    });
    if (d) svg += `<path d="${d}" fill="none" style="stroke:var(${col})" stroke-width="1.6" stroke-linejoin="round" opacity=".9"/>`;
  });
  // support / resistance bands (C), drawn under the candles
  levels.forEach(([kind, g]) => {
    const y1 = Y(g.hi + g.level * 0.002), y2 = Y(g.lo - g.level * 0.002);
    svg += `<rect x="${padL}" y="${y1.toFixed(1)}" width="${plotW}" height="${Math.max(2, y2 - y1).toFixed(1)}" style="fill:var(--ink-faint)" opacity=".16"/>`;
    svg += `<line x1="${padL}" x2="${W - padR}" y1="${Y(g.level).toFixed(1)}" y2="${Y(g.level).toFixed(1)}" style="stroke:var(--ink-soft)" stroke-width="1" opacity=".7"/>`;
    tags.push({ y: Y(g.level), text: (kind === 'resist' ? '壓' : '撐') + nfmt(g.level), fill: '--ink-faint', ink: '--paper' });
  });
  // trend lines (A): from the first swing point (or the left edge) to today
  tlines.forEach(([kind, t]) => {
    const s0 = Math.max(from, t.i1), s1 = to - 1;
    const xa = X(s0 - from), xb = X(s1 - from);
    svg += `<line x1="${xa.toFixed(1)}" x2="${xb.toFixed(1)}" y1="${Y(t.at(s0)).toFixed(1)}" y2="${Y(t.at(s1)).toFixed(1)}" style="stroke:var(--accent)" stroke-width="1.6" stroke-dasharray="7 4"/>`;
    [t.i1, t.i2].forEach(i => {
      if (i >= from) svg += `<circle cx="${X(i - from).toFixed(1)}" cy="${Y(t.at(i)).toFixed(1)}" r="3.5" style="fill:var(--paper);stroke:var(--accent)" stroke-width="1.5"/>`;
    });
    tags.push({ y: Y(t.at(s1)), text: nfmt(t.at(s1)), fill: '--paper', ink: '--accent', outline: true });
  });
  // candles (TW convention: red up, green down)
  dates.forEach((d, i) => {
    if (c[i] === null || c[i] === undefined) return;
    const op = o[i] ?? c[i], hh = hi[i], ll = lo[i];
    const up = c[i] >= op;
    const col = up ? '--rise' : '--fall';
    const x = X(i).toFixed(1);
    svg += `<line x1="${x}" x2="${x}" y1="${Y(hh).toFixed(1)}" y2="${Y(ll).toFixed(1)}" style="stroke:var(${col})" stroke-width="1"/>`;
    const top = Y(Math.max(op, c[i])), bot = Y(Math.min(op, c[i]));
    const hollow = up && bw >= 4;  // hollow red bodies for up days when there is room
    svg += `<rect x="${(X(i) - bw / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, bot - top).toFixed(1)}" style="fill:var(${hollow ? '--paper' : col});stroke:var(${col})" stroke-width="1"/>`;
  });
  // signal markers: ▲ under the low for strong-trend signals, ▼ over the high for weak-trend ones
  const tri = (x, y, down, col) => {
    const s = 5;
    return down
      ? `<path d="M${x - s},${y - s * 1.6}L${x + s},${y - s * 1.6}L${x},${y}Z" style="fill:var(${col})"/>`
      : `<path d="M${x - s},${y + s * 1.6}L${x + s},${y + s * 1.6}L${x},${y}Z" style="fill:var(${col})"/>`;
  };
  dates.forEach((d, i) => {
    const codes = byDate[d] || [];
    if (c[i] === null || c[i] === undefined) return;
    const x = X(i);
    if (codes.some(x2 => MARK_UP.has(x2))) svg += tri(x, Y(lo[i]) + 4, false, '--rise');
    if (codes.some(x2 => MARK_DN.has(x2))) svg += tri(x, Y(hi[i]) - 4, true, '--fall');
  });
  // last close tag on the axis
  let last = n - 1;
  while (last >= 0 && (c[last] === null || c[last] === undefined)) last--;
  if (last >= 0) {
    const y = Y(c[last]);
    const up = (last > 0 ? c[last - 1] : prevC) === null ? true : c[last] >= (last > 0 ? c[last - 1] : prevC);
    // Panned into the past: the right edge is not today, so mark it quietly instead of as the price.
    if (!scEnd) svg += `<line x1="${padL}" x2="${W - padR}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" style="stroke:var(${up ? '--rise' : '--fall'})" stroke-dasharray="2 3" opacity=".7"/>`;
    tags.push({ y, text: nfmt(c[last]), fill: scEnd ? '--ink-faint' : up ? '--rise' : '--fall', ink: '--paper', fixed: true });
  }
  // lay the gutter tags out top to bottom, 19px apart, keeping the last-close tag where it is
  tags.sort((a, b) => a.y - b.y);
  const fixedTag = tags.find(t => t.fixed);
  for (let k = 1; k < tags.length; k++) if (!tags[k].fixed && tags[k].y < tags[k - 1].y + 19) tags[k].y = tags[k - 1].y + 19;
  for (let k = tags.length - 2; k >= 0; k--) if (!tags[k].fixed && tags[k].y > tags[k + 1].y - 19) tags[k].y = tags[k + 1].y - 19;
  if (fixedTag) for (let k = 1; k < tags.length; k++) if (!tags[k].fixed && tags[k].y < tags[k - 1].y + 19) tags[k].y = tags[k - 1].y + 19;
  tags.forEach(t => {
    svg += `<rect x="${W - padR + 2}" y="${(t.y - 9).toFixed(1)}" width="${padR - 3}" height="18" rx="3" style="fill:var(${t.fill})${t.outline ? ';stroke:var(--accent)' : ''}" stroke-width="1.2"/>`;
    svg += `<text x="${W - padR + 5}" y="${(t.y + 4).toFixed(1)}" style="fill:var(${t.ink});font:600 11px 'IBM Plex Mono','PingFang TC',monospace">${t.text}</text>`;
  });
  svg += `<line class="xh" y1="${padT}" y2="${vTop + volH}" x1="0" x2="0" visibility="hidden"/></svg>`;

  const tlTip = i => tlines.filter(([, t]) => from + i >= t.i1)
    .map(([kind, t]) => `<div><i class="sw" style="background:var(--accent)"></i>${kind === 'res' ? '壓力線' : '支撐線'} <b>${nfmt(t.at(from + i))}</b></div>`).join('');
  const tip = i => {
    const d = dates[i];
    const prev = i > 0 ? c[i - 1] : prevC;
    const chg = c[i] !== null && prev ? (c[i] / prev - 1) * 100 : null;
    const chgHtml = chg === null ? '' : ` <b style="color:var(${chg >= 0 ? '--rise' : '--fall'})">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</b>`;
    const codes = byDate[d] || [];
    const sig = codes.length ? '<div style="margin-top:3px;white-space:normal;max-width:220px">' + codes.map(x => esc(SIGLABEL[x] || x)).join('、') + '</div>' : '';
    return `<div><b>${d}</b>${chgHtml}</div>
      <div>開 <b>${nfmt(o[i])}</b> 高 <b>${nfmt(h[i])}</b></div>
      <div>低 <b>${nfmt(l[i])}</b> 收 <b>${nfmt(c[i])}</b></div>
      <div>量 <b>${vfmt(v[i])}</b>${VOL_UNIT}</div>
      <div><i class="sw" style="background:var(--warn)"></i>月線 <b>${nfmt(m[i])}</b> <i class="sw" style="background:var(--info);margin-left:6px"></i>季線 <b>${nfmt(q[i])}</b></div>${tlTip(i)}${sig}`;
  };
  CHART_REG[id] = { spec: { tip }, W, padL, plotW, n, X, dates, idx: px => Math.floor((px - padL) / slot) };

  // headline: last close and change over the visible range
  const first = c.find(x => x !== null && x !== undefined);
  const visLast = last >= 0 ? c[last] : null;
  let fl = ser.c.length - 1;
  while (fl >= 0 && (ser.c[fl] === null || ser.c[fl] === undefined)) fl--;
  const lastC = fl >= 0 ? ser.c[fl] : null;
  let fp = fl - 1;
  while (fp >= 0 && (ser.c[fp] === null || ser.c[fp] === undefined)) fp--;
  const dayPrev = fp >= 0 ? ser.c[fp] : null;
  const pct = (a, b) => a !== null && b ? (a / b - 1) * 100 : null;
  const pill = (label, val) => val === null ? '' :
    `<span class="sc-chg" style="color:var(${val >= 0 ? '--rise' : '--fall'})">${label} ${val >= 0 ? '+' : ''}${val.toFixed(1)}%</span>`;
  const optBtn = (k, lab) => `<button type="button" class="opt${scOpt[k] ? ' active' : ''}" data-sc-opt="${k}" aria-pressed="${scOpt[k]}">${scOpt[k] ? '✓ ' : '+ '}${lab}</button>`;
  const notes = [];
  if (scOpt.tl && !ov.res) notes.push('目前沒有有效的下降壓力線');
  if (scOpt.tl && !ov.sup) notes.push('目前沒有有效的上升支撐線');
  if (scOpt.sr && !ov.lv.resist) notes.push('上方沒有碰過兩次以上的壓力價位');
  if (scOpt.sr && !ov.lv.support) notes.push('下方沒有碰過兩次以上的支撐價位');
  const chips = SC_RANGES.filter(r => r[0] <= total || r[0] === SC_RANGES[0][0])
    .map(([k, lab]) => { const on = k === span && !scEnd; return `<button type="button" class="${on ? 'active' : ''}" data-sc-range="${k}" aria-pressed="${on}">${lab}</button>`; }).join('');
  const zoomBtns = `<button type="button" class="zb" data-sc-zoom="out" aria-label="縮小(看更長期間)"${span >= total ? ' disabled' : ''}>－</button>`
    + `<button type="button" class="zb" data-sc-zoom="in" aria-label="放大(看更少天)"${span <= SC_MIN_SPAN ? ' disabled' : ''}>＋</button>`
    + (scEnd ? `<button type="button" data-sc-zoom="latest">回到最新 ›</button>` : '');
  return `<div class="sc-head">
      <div class="sc-price"><b>${nfmt(lastC)}</b>${pill('當日', pct(lastC, dayPrev))}${pill(scEnd ? `${mdLabel(dates[0])}~${mdLabel(dates[n - 1])}` : '區間', pct(visLast, first))}</div>
      <div class="sc-ctrl">
        <div class="chips" role="group" aria-label="期間">${chips}</div>
        <div class="chips" role="group" aria-label="縮放">${zoomBtns}</div>
        <div class="chips" role="group" aria-label="輔助線">${optBtn('tl', '切線')}${optBtn('sr', '支撐壓力')}</div>
      </div>
    </div>
    <div class="chart" data-id="${id}">${svg}<div class="tip" hidden></div></div>
    <p class="sc-hint">點K棒看當天數值・左右拖曳平移・雙指或 Ctrl/⌘＋滾輪縮放</p>
    <div class="key-row">
      <span><i class="cdl" style="border-color:var(--rise)"></i>上漲</span>
      <span><i class="cdl" style="background:var(--fall);border-color:var(--fall)"></i>下跌</span>
      <span><i class="sw" style="border-color:var(--warn)"></i>月線(20日)</span>
      <span><i class="sw" style="border-color:var(--info)"></i>季線(60日)</span>
      <span style="color:var(--rise)">▲ 強勢趨勢訊號</span>
      <span style="color:var(--fall)">▼ 弱勢趨勢訊號</span>
      <span><i class="dot" style="background:var(--vol);border-radius:2px"></i>量能異常</span>
      ${scOpt.tl ? '<span><i class="sw" style="border-color:var(--accent);border-top-style:dashed"></i>切線(○為連線的轉折點,右側框線標籤=今天的位置)</span>' : ''}
      ${scOpt.sr ? '<span><i class="dot" style="background:var(--ink-faint);opacity:.5;border-radius:2px"></i>支撐/壓力帶(右側「撐/壓」標籤,碰過2次以上)</span>' : ''}
    </div>
    ${notes.length || scOpt.tl || scOpt.sr ? `<p class="sc-note">${notes.length ? esc(notes.join('；')) + '。' : ''}${scOpt.tl || scOpt.sr ? '輔助線依近6個月轉折點自動畫出,只供參考,沒有回測、不列為訊號。' : ''}</p>` : ''}`;
}

document.addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('[data-sc-range],[data-sc-opt],[data-sc-zoom]');
  if (!btn) return;
  if (btn.dataset.scZoom) {
    const z = btn.dataset.scZoom;
    if (z === 'latest') setView(scSpan(), 0);
    else zoomTo(scSpan() * (z === 'in' ? 0.6 : 1 / 0.6), 1, scSpan(), scEnd);  // keep the right edge
    return;
  }
  if (btn.dataset.scOpt) {
    scOpt[btn.dataset.scOpt] = !scOpt[btn.dataset.scOpt];
    try { localStorage.setItem('sc-opt', JSON.stringify(scOpt)); } catch (err) {}
  } else {
    scRange = +btn.dataset.scRange; scEnd = 0;
    try { localStorage.setItem('sc-range', String(scRange)); } catch (err) {}
  }
  redrawStockCharts();
});

function stockChartHtml(stock) {
  const ser = SER.v && SER.v[stock.stock_id];
  if (!ser || SER.dates.length < 2) return '';
  if (!ser.o) {  // older payload (close + 20-day line only)
    ser.o = ser.c; ser.h = ser.c; ser.l = ser.c; ser.v = ser.c.map(() => null); ser.q = ser.c.map(() => null);
  }
  return `<div class="sc-box" data-sid="${esc(stock.stock_id)}">${candleChart(stock, ser, stockSignalsByDate(stock.stock_id))}</div>`;
}

function stockHistoryHtml(stock) {
  const byDate = stockSignalsByDate(stock.stock_id);
  const dates = Object.keys(byDate).sort().reverse();
  const horizon = HIST.days.length;
  const rows = dates.slice(0, 12).map(d => {
    const badges = byDate[d].map(c => `<span class="badge" style="${badgeStyle(codeCategory(c))}">${esc(SIGLABEL[c] || c)}</span>`).join('');
    return `<div class="hist-row"><span class="hd">${mdLabel(d)}</span><span class="hb">${badges}</span></div>`;
  }).join('');
  const more = dates.length > 12 ? `<p class="hist-empty" style="margin-top:6px">只列最近 12 天,其餘共 ${dates.length - 12} 天有訊號。</p>` : '';
  const list = dates.length ? rows + more : `<p class="hist-empty">近 ${horizon} 個交易日沒有觸發任何訊號。</p>`;
  return `<div class="history">
    <h3>訊號紀錄(近 ${horizon} 個交易日)</h3>
    ${list}
  </div>`;
}

let resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { renderTrend(); render(); }, 150);
});
"""
