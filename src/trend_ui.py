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
.sc-box .chart { touch-action: pan-y; }
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

function chartPointer(e) {
  const wrap = e.target.closest && e.target.closest('.chart');
  if (!wrap) { hideTips(null); return; }
  hideTips(wrap);
  const reg = CHART_REG[wrap.dataset.id];
  if (!reg) return;
  const svg = wrap.querySelector('svg');
  const rect = svg.getBoundingClientRect();
  const px = (e.clientX - rect.left) * (reg.W / rect.width);
  let i = reg.idx ? reg.idx(px) : Math.round((px - reg.padL) / reg.plotW * (reg.n - 1));
  i = Math.max(0, Math.min(reg.n - 1, i));
  const x = reg.X(i);
  const xh = wrap.querySelector('.xh');
  xh.setAttribute('x1', x); xh.setAttribute('x2', x); xh.setAttribute('visibility', 'visible');
  const tip = wrap.querySelector('.tip');
  tip.innerHTML = reg.spec.tip(i);
  tip.hidden = false;
  const scale = rect.width / reg.W;
  const tw = tip.offsetWidth;
  let left = x * scale + 12;
  if (left + tw > rect.width) left = x * scale - tw - 12;
  tip.style.left = Math.max(0, left) + 'px';
}
document.addEventListener('pointermove', chartPointer);
document.addEventListener('pointerdown', chartPointer);

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

const nfmt = v => v === null || v === undefined ? '—' : (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-US') : String(+(+v).toFixed(2)));
const vfmt = v => {
  if (v === null || v === undefined) return '—';
  const a = Math.abs(v);
  return a >= 1e9 ? (v / 1e9).toFixed(1) + 'B' : a >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : a >= 1e4 ? (v / 1e3).toFixed(0) + 'K' : nfmt(v);
};

function candleChart(stock, ser, byDate) {
  const id = 'ch' + (++chartSeq);
  const total = SER.dates.length;
  const from = Math.max(0, total - scRange);
  const dates = SER.dates.slice(from);
  const cut = k => (ser[k] || []).slice(from);
  const o = cut('o'), h = cut('h'), l = cut('l'), c = cut('c'), v = cut('v'), m = cut('m'), q = cut('q');
  const prevC = from > 0 ? ser.c[from - 1] : null;
  const n = dates.length;
  const W = chartWidth();
  const narrow = W < 420;
  const padL = 8, padR = 52, padT = 14;
  const priceH = narrow ? 210 : 250, gap = 10, volH = narrow ? 46 : 56, padB = 22;
  const H = padT + priceH + gap + volH + padB;
  const plotW = W - padL - padR;
  const slot = plotW / n;
  const X = i => padL + (i + 0.5) * slot;
  const hi = h.map((x, i) => x ?? c[i]), lo = l.map((x, i) => x ?? c[i]);
  const pv = [...hi, ...lo, ...m, ...q].filter(x => x !== null && x !== undefined);
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
  const vmax = Math.max(1, ...v.filter(x => x !== null && x !== undefined));
  const vTop = padT + priceH + gap;
  const VY = val => vTop + volH - (val / vmax) * volH;
  const bw = Math.max(1, Math.min(14, slot * 0.64));

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(stock.name)} K線、成交量與均線">`;
  // grid + right-side price axis
  ax.ticks.forEach(t => {
    const y = Y(t).toFixed(1);
    svg += `<line class="gl" x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}"/>`;
    if (Math.abs(+y - tagY) > 13) svg += `<text class="ax" x="${W - padR + 6}" y="${+y + 4}">${nfmt(t)}</text>`;
  });
  svg += `<line class="gl" x1="${padL}" x2="${W - padR}" y1="${vTop + volH}" y2="${vTop + volH}"/>`;
  svg += `<text class="ax" x="${W - padR + 6}" y="${vTop + 9}">${vfmt(vmax)}</text>`;
  // month ticks on the x axis
  let lastMonth = '';
  const minGap = narrow ? 52 : 64;
  let lastX = -1e9;
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
    svg += `<line x1="${padL}" x2="${W - padR}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" style="stroke:var(${up ? '--rise' : '--fall'})" stroke-dasharray="2 3" opacity=".7"/>`;
    svg += `<rect x="${W - padR + 2}" y="${(y - 9).toFixed(1)}" width="${padR - 2}" height="18" rx="3" style="fill:var(${up ? '--rise' : '--fall'})"/>`;
    svg += `<text x="${W - padR + 6}" y="${(y + 4).toFixed(1)}" style="fill:var(--paper);font:600 11px 'IBM Plex Mono',monospace">${nfmt(c[last])}</text>`;
  }
  svg += `<line class="xh" y1="${padT}" y2="${vTop + volH}" x1="0" x2="0" visibility="hidden"/></svg>`;

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
      <div><i class="sw" style="background:var(--warn)"></i>月線 <b>${nfmt(m[i])}</b> <i class="sw" style="background:var(--info);margin-left:6px"></i>季線 <b>${nfmt(q[i])}</b></div>${sig}`;
  };
  CHART_REG[id] = { spec: { tip }, W, padL, plotW, n, X, idx: px => Math.floor((px - padL) / slot) };

  // headline: last close and change over the visible range
  const first = c.find(x => x !== null && x !== undefined);
  const lastC = last >= 0 ? c[last] : null;
  const dayPrev = last > 0 ? c[last - 1] : prevC;
  const pct = (a, b) => a !== null && b ? (a / b - 1) * 100 : null;
  const pill = (label, val) => val === null ? '' :
    `<span class="sc-chg" style="color:var(${val >= 0 ? '--rise' : '--fall'})">${label} ${val >= 0 ? '+' : ''}${val.toFixed(1)}%</span>`;
  const chips = SC_RANGES.filter(r => r[0] <= total || r[0] === SC_RANGES[0][0])
    .map(([k, lab]) => `<button type="button" class="${k === scRange ? 'active' : ''}" data-sc-range="${k}" aria-pressed="${k === scRange}">${lab}</button>`).join('');
  return `<div class="sc-head">
      <div class="sc-price"><b>${nfmt(lastC)}</b>${pill('當日', pct(lastC, dayPrev))}${pill('區間', pct(lastC, first))}</div>
      <div class="chips" role="group" aria-label="期間">${chips}</div>
    </div>
    <div class="chart" data-id="${id}">${svg}<div class="tip" hidden></div></div>
    <div class="key-row">
      <span><i class="cdl" style="border-color:var(--rise)"></i>上漲</span>
      <span><i class="cdl" style="background:var(--fall);border-color:var(--fall)"></i>下跌</span>
      <span><i class="sw" style="border-color:var(--warn)"></i>月線(20日)</span>
      <span><i class="sw" style="border-color:var(--info)"></i>季線(60日)</span>
      <span style="color:var(--rise)">▲ 強勢趨勢訊號</span>
      <span style="color:var(--fall)">▼ 弱勢趨勢訊號</span>
      <span><i class="dot" style="background:var(--vol);border-radius:2px"></i>量能異常</span>
    </div>`;
}

document.addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('[data-sc-range]');
  if (!btn) return;
  scRange = +btn.dataset.scRange;
  try { localStorage.setItem('sc-range', String(scRange)); } catch (err) {}
  document.querySelectorAll('.sc-box').forEach(box => {
    const stock = STOCKS.find(s => s.stock_id === box.dataset.sid);
    if (stock) box.innerHTML = candleChart(stock, SER.v[stock.stock_id], stockSignalsByDate(stock.stock_id));
  });
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
