import csv
import json
from collections import Counter
from pathlib import Path

SIGNAL_ORDER = [
    "ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high",
    "ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low",
    "rsi_overbought", "rsi_oversold", "volume_spike",
]

SIGNAL_SECTION_TITLE = {
    "ma_golden_cross": "均線黃金交叉",
    "macd_golden_cross": "MACD金叉",
    "bb_breakout_upper": "突破布林上軌",
    "new_high": "創60日新高",
    "ma_death_cross": "均線死亡交叉",
    "macd_death_cross": "MACD死叉",
    "bb_breakout_lower": "跌破布林下軌",
    "new_low": "創60日新低",
    "rsi_overbought": "RSI超買(短線過熱)",
    "rsi_oversold": "RSI超賣(短線超跌)",
    "volume_spike": "成交量異常放大",
}

BULLISH_SIGNALS = {"ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high"}
BEARISH_SIGNALS = {"ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low"}

FILTER_CATEGORIES = {
    "bull": {"label": "偏多", "codes": ["ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high"], "bg": "#E1F5EE", "text": "#04342C"},
    "bear": {"label": "偏空", "codes": ["ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low"], "bg": "#FAECE7", "text": "#4A1B0C"},
    "overbought": {"label": "RSI超買", "codes": ["rsi_overbought"], "bg": "#FAEEDA", "text": "#412402"},
    "oversold": {"label": "RSI超賣", "codes": ["rsi_oversold"], "bg": "#E6F1FB", "text": "#042C53"},
    "volume": {"label": "成交量異常", "codes": ["volume_spike"], "bg": "#EEEDFE", "text": "#26215C"},
}

ARTIFACT_CATEGORIES = {
    "bull": {"label": "偏多", "codes": ["ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high"], "varBg": "--rise-soft", "varText": "--rise"},
    "bear": {"label": "偏空", "codes": ["ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low"], "varBg": "--fall-soft", "varText": "--fall"},
    "overbought": {"label": "RSI超買", "codes": ["rsi_overbought"], "varBg": "--warn-soft", "varText": "--warn"},
    "oversold": {"label": "RSI超賣", "codes": ["rsi_oversold"], "varBg": "--info-soft", "varText": "--info"},
    "volume": {"label": "成交量異常", "codes": ["volume_spike"], "varBg": "--vol-soft", "varText": "--vol"},
}


def _group_by_signal(alerts: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {code: [] for code in SIGNAL_ORDER}
    for a in alerts:
        groups.setdefault(a["signal"], []).append(a)
    return groups


def _group_by_stock(alerts: list[dict]) -> dict:
    by_stock: dict[str, dict] = {}
    for a in alerts:
        entry = by_stock.setdefault(a["stock_id"], {"name": a["stock_name"], "signals": []})
        entry["signals"].append(a["detail"])
    return by_stock


def _top_industries(stock_ids: set, industry_map: dict, top_n: int = 2) -> list[str]:
    counter = Counter(industry_map.get(sid, "其他") for sid in stock_ids)
    return [f"{name}({cnt}檔)" for name, cnt in counter.most_common(top_n)]


def build_market_narrative(alerts: list[dict], universe: list[dict], total_universe: int) -> str:
    industry_map = {s["stock_id"]: s.get("industry", "其他") for s in universe}
    by_stock = _group_by_stock(alerts)

    bullish_ids = {a["stock_id"] for a in alerts if a["signal"] in BULLISH_SIGNALS}
    bearish_ids = {a["stock_id"] for a in alerts if a["signal"] in BEARISH_SIGNALS}
    overbought_ids = {a["stock_id"] for a in alerts if a["signal"] == "rsi_overbought"}
    oversold_ids = {a["stock_id"] for a in alerts if a["signal"] == "rsi_oversold"}
    volume_ids = {a["stock_id"] for a in alerts if a["signal"] == "volume_spike"}

    if not by_stock:
        return f"今日監測{total_universe}檔,無任何個股觸發技術訊號,市場訊號平靜。"

    pct = len(by_stock) / total_universe * 100
    lines = [f"今日監測{total_universe}檔,共{len(by_stock)}檔觸發技術訊號(占比{pct:.0f}%)。"]

    if bullish_ids:
        industries = "、".join(_top_industries(bullish_ids, industry_map))
        lines.append(f"偏多訊號(創新高/黃金交叉/突破布林上軌)共{len(bullish_ids)}檔,以{industries}居多。")
    if bearish_ids:
        industries = "、".join(_top_industries(bearish_ids, industry_map))
        lines.append(f"偏空訊號(創新低/死亡交叉/跌破布林下軌)共{len(bearish_ids)}檔,以{industries}居多。")

    if len(bullish_ids) > len(bearish_ids) * 1.2:
        lines.append("整體訊號偏多。")
    elif len(bearish_ids) > len(bullish_ids) * 1.2:
        lines.append("整體訊號偏空。")
    elif bullish_ids or bearish_ids:
        lines.append("多空訊號互見,無明顯方向。")

    if overbought_ids or oversold_ids:
        lines.append(f"RSI超買{len(overbought_ids)}檔、超賣{len(oversold_ids)}檔。")
    if volume_ids:
        industries = "、".join(_top_industries(volume_ids, industry_map))
        lines.append(f"成交量異常放大共{len(volume_ids)}檔,以{industries}居多,值得留意資金是否轉向。")

    return " ".join(lines)


def write_csv_report(report_dir: str, run_date: str, alerts: list[dict]) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{run_date}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["股票代號", "股票名稱", "訊號", "說明"])
        for a in alerts:
            writer.writerow([a["stock_id"], a["stock_name"], a["signal"], a["detail"]])
    return str(path)


def _build_unified_payload(alerts: list[dict], universe: list[dict], news_map: dict | None = None,
                            snapshots: list[dict] | None = None) -> list[dict]:
    """One record per stock that has a snapshot for the day (all monitored stocks, not just
    triggered ones) — powers both the triggered-signal browsing view and the by-name/code search."""
    industry_map = {s["stock_id"]: s.get("industry", "其他") for s in universe}
    news_map = news_map or {}

    signals_by_stock: dict[str, list[dict]] = {}
    for a in alerts:
        signals_by_stock.setdefault(a["stock_id"], []).append({"code": a["signal"], "detail": a["detail"]})

    if snapshots:
        payload = []
        for snap in snapshots:
            sid = snap["stock_id"]
            payload.append(
                {
                    **snap,
                    "industry": industry_map.get(sid, "其他"),
                    "signals": signals_by_stock.get(sid, []),
                    "news": news_map.get(sid, []),
                }
            )
        return payload

    # Fallback (no snapshots supplied): triggered stocks only, no indicator values.
    by_stock: dict[str, dict] = {}
    for a in alerts:
        entry = by_stock.setdefault(
            a["stock_id"],
            {"stock_id": a["stock_id"], "name": a["stock_name"], "industry": industry_map.get(a["stock_id"], "其他"),
             "signals": [], "news": news_map.get(a["stock_id"], [])},
        )
        entry["signals"].append({"code": a["signal"], "detail": a["detail"]})
    return list(by_stock.values())


_SEARCH_SCRIPT = """
function normalize(s) { return (s || '').toString().toLowerCase(); }
function matchesSearch(stock, q) {
  q = normalize(q).trim();
  return stock.stock_id.includes(q) || normalize(stock.name).includes(q);
}
function fmt(v, suffix) {
  return (v === null || v === undefined) ? '—' : (v + (suffix || ''));
}
"""


_ROW_HTML_LOCAL = (
    '<td style="font-weight:500;white-space:nowrap">${stock.stock_id}</td>'
    '<td style="white-space:nowrap">${stock.name}</td>'
    '<td style="color:var(--text-secondary);white-space:nowrap">${stock.industry}</td>'
    '<td>${badges}${newsHtml}</td>'
)

_MINI_STATS = [
    ("收盤", "close", ""), ("MA5", "ma5", ""), ("MA20", "ma20", ""), ("MA60", "ma60", ""), ("RSI", "rsi", ""),
    ("MACD", "macd", ""), ("MACD訊號", "macd_signal", ""), ("布林上軌", "bb_upper", ""), ("布林下軌", "bb_lower", ""),
    ("量比", "vol_ratio", "x"),
]

_CARD_STATS_JS = "[" + ",".join(f'["{label}","{key}","{suffix}"]' for label, key, suffix in _MINI_STATS) + "]"

_CARD_HTML_FN = f"""
function cardHtml(stock) {{
  const badges = stock.signals.map(sig => {{
    const cat = codeCategory(sig.code);
    const style = badgeStyle(cat);
    return `<span class="badge" style="${{style}}">${{sig.detail}}</span>`;
  }}).join('');
  const badgesHtml = badges ? `<div class="stock-card-badges">${{badges}}</div>` : '';
  const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join('');
  const newsHtml = news ? `<div class="news">${{news}}</div>` : '';
  const grid = {_CARD_STATS_JS}.map(([label, key, suffix]) =>
    `<div class="mini-stat"><p class="label">${{label}}</p><p class="value">${{fmt(stock[key], suffix)}}</p></div>`
  ).join('');
  return `<div class="stock-card">
    <div class="stock-card-head"><span class="code">${{stock.stock_id}}</span><span class="name">${{stock.name}}</span><span class="industry">${{stock.industry}}</span></div>
    ${{badgesHtml}}
    <div class="mini-grid">${{grid}}</div>
    ${{newsHtml}}
  </div>`;
}}
"""


def write_html_report(report_dir: str, run_date: str, alerts: list[dict], universe: list[dict],
                       news_map: dict | None = None, snapshots: list[dict] | None = None) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{run_date}.html"

    narrative = build_market_narrative(alerts, universe, len(universe))
    bullish_ids = {a["stock_id"] for a in alerts if a["signal"] in BULLISH_SIGNALS}
    bearish_ids = {a["stock_id"] for a in alerts if a["signal"] in BEARISH_SIGNALS}
    triggered_count = len({a["stock_id"] for a in alerts})
    payload = _build_unified_payload(alerts, universe, news_map, snapshots)

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股監測報表 {run_date}</title>
<style>
:root {{
  --bg: #ffffff; --card: #f5f5f4; --text: #1a1a1a; --text-secondary: #6b6b68;
  --border: #e2e2df; --border-strong: #c7c7c3; --accent-bg: #e6f1fb; --accent-text: #185fa5;
  --success: #0f6e56; --danger: #993c1d;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #1c1c1a; --card: #292926; --text: #f0f0ee; --text-secondary: #a8a8a4;
    --border: #3a3a37; --border-strong: #4d4d49; --accent-bg: #0c447c; --accent-text: #b5d4f4;
    --success: #5dcaa5; --danger: #f0997b; }}
}}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "PingFang TC", sans-serif; margin: 0; padding: 24px; background: var(--bg); color: var(--text); max-width: 960px; }}
h1 {{ font-size: 20px; font-weight: 500; margin: 0 0 16px; }}
.narrative {{ background: var(--card); padding: 16px; border-radius: 12px; line-height: 1.7; margin-bottom: 20px; font-size: 14px; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }}
.stat {{ background: var(--card); border-radius: 12px; padding: 14px; }}
.stat .label {{ font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; }}
.stat .value {{ font-size: 22px; font-weight: 500; margin: 0; }}
.search {{ display: flex; gap: 8px; margin-bottom: 14px; }}
.search input {{ flex: 1; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--bg); color: var(--text); font-size: 14px; font-family: inherit; }}
.search button {{ border-radius: 8px; border: 1px solid var(--border-strong); background: transparent; color: var(--text-secondary); padding: 6px 14px; font-size: 13px; cursor: pointer; font-family: inherit; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
.filters button {{ border-radius: 8px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); padding: 6px 14px; font-size: 13px; cursor: pointer; font-family: inherit; }}
.filters button.active {{ border-color: var(--accent-text); background: var(--accent-bg); color: var(--accent-text); }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th {{ text-align: left; padding: 8px 10px; color: var(--text-secondary); font-weight: 500; border-bottom: 1px solid var(--border-strong); }}
td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
.badge {{ display: inline-block; border-radius: 8px; padding: 2px 8px; font-size: 12px; margin: 2px 4px 2px 0; white-space: nowrap; }}
.news {{ margin-top: 4px; font-size: 12px; }}
.news a {{ color: var(--accent-text); text-decoration: none; display: block; margin: 2px 0; }}
.news a:hover {{ text-decoration: underline; }}
.cards {{ display: flex; flex-direction: column; gap: 12px; }}
.stock-card {{ background: var(--card); border-radius: 12px; padding: 16px; }}
.stock-card-head {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }}
.stock-card-head .code {{ font-weight: 500; font-size: 16px; }}
.stock-card-head .name {{ font-size: 16px; }}
.stock-card-head .industry {{ font-size: 12px; color: var(--text-secondary); }}
.stock-card-badges {{ margin-bottom: 10px; }}
.mini-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 8px; }}
.mini-stat {{ background: var(--bg); border-radius: 8px; padding: 8px 10px; }}
.mini-stat .label {{ font-size: 11px; color: var(--text-secondary); margin: 0 0 2px; }}
.mini-stat .value {{ font-size: 15px; font-weight: 500; margin: 0; }}
#empty-msg {{ display: none; color: var(--text-secondary); font-size: 13px; padding: 16px 0; }}
@media (max-width: 560px) {{ .mini-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
</style></head>
<body>
<h1>台股技術指標監測報表 — {run_date}</h1>
<div class="narrative">{narrative}</div>

<div class="stats">
  <div class="stat"><p class="label">監測檔數</p><p class="value">{len(universe)}</p></div>
  <div class="stat"><p class="label">觸發訊號</p><p class="value">{triggered_count}</p></div>
  <div class="stat"><p class="label">偏多訊號</p><p class="value" style="color:var(--success)">{len(bullish_ids)}</p></div>
  <div class="stat"><p class="label">偏空訊號</p><p class="value" style="color:var(--danger)">{len(bearish_ids)}</p></div>
</div>

<div class="search">
  <input type="text" id="search-input" placeholder="搜尋代號或名稱(例如 2330 或 台積電),查任一檔目前指標數值">
  <button type="button" id="search-clear">清除</button>
</div>

<div id="filters" class="filters"></div>
<div id="table-wrap">
<table>
  <thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>觸發訊號</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
</div>
<div id="cards" class="cards" style="display:none"></div>
<p id="empty-msg"></p>

<script>
const STOCKS = {json.dumps(payload, ensure_ascii=False)};
const CATS = {json.dumps(FILTER_CATEGORIES, ensure_ascii=False)};
{_SEARCH_SCRIPT}
function codeCategory(code) {{
  for (const key in CATS) {{ if (CATS[key].codes.includes(code)) return key; }}
  return null;
}}
function stockCats(stock) {{
  const s = new Set();
  stock.signals.forEach(sig => {{ const c = codeCategory(sig.code); if (c) s.add(c); }});
  return s;
}}
function badgeStyle(cat) {{
  return cat ? `background:${{CATS[cat].bg}};color:${{CATS[cat].text}}` : 'background:var(--card);color:var(--text-secondary)';
}}
{_CARD_HTML_FN}

let activeFilter = 'all';
let searchQuery = '';

function renderFilters() {{
  const el = document.getElementById('filters');
  if (searchQuery.trim()) {{ el.style.display = 'none'; return; }}
  el.style.display = 'flex';
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  const counts = {{ all: triggered.length }};
  Object.keys(CATS).forEach(k => {{ counts[k] = triggered.filter(a => stockCats(a).has(k)).length; }});
  el.innerHTML = '';
  const items = [['all', '全部']].concat(Object.keys(CATS).map(k => [k, CATS[k].label]));
  items.forEach(([key, label]) => {{
    const btn = document.createElement('button');
    btn.textContent = `${{label}} (${{counts[key]}})`;
    btn.className = key === activeFilter ? 'active' : '';
    btn.onclick = () => {{ activeFilter = key; render(); }};
    el.appendChild(btn);
  }});
}}

function getVisible() {{
  if (searchQuery.trim()) {{
    return STOCKS.filter(s => matchesSearch(s, searchQuery));
  }}
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  return activeFilter === 'all' ? triggered : triggered.filter(s => stockCats(s).has(activeFilter));
}}

function render() {{
  renderFilters();
  const visible = getVisible();
  const searching = searchQuery.trim().length > 0;
  const emptyMsg = document.getElementById('empty-msg');
  const tableWrap = document.getElementById('table-wrap');
  const cardsWrap = document.getElementById('cards');

  if (!visible.length) {{
    emptyMsg.style.display = 'block';
    emptyMsg.textContent = searching
      ? `查無「${{searchQuery}}」相關股票(僅收錄台灣50+中型100共{len(universe)}檔)`
      : '沒有符合這個篩選條件的股票。';
  }} else {{
    emptyMsg.style.display = 'none';
  }}

  tableWrap.style.display = searching ? 'none' : 'block';
  cardsWrap.style.display = searching ? 'flex' : 'none';

  if (searching) {{
    cardsWrap.innerHTML = visible.map(cardHtml).join('');
    return;
  }}

  const rows = document.getElementById('rows');
  rows.innerHTML = '';
  visible.forEach(stock => {{
    const tr = document.createElement('tr');
    const badges = stock.signals.map(sig => `<span class="badge" style="${{badgeStyle(codeCategory(sig.code))}}">${{sig.detail}}</span>`).join('');
    const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join('');
    const newsHtml = news ? `<div class="news">${{news}}</div>` : '';
    tr.innerHTML = `{_ROW_HTML_LOCAL}`;
    rows.appendChild(tr);
  }});
}}

document.getElementById('search-input').addEventListener('input', (e) => {{ searchQuery = e.target.value; render(); }});
document.getElementById('search-clear').addEventListener('click', () => {{ searchQuery = ''; document.getElementById('search-input').value = ''; render(); }});
render();
</script>
</body></html>"""
    path.write_text(html, encoding="utf-8")
    return str(path)


_ROW_HTML_ARTIFACT = (
    '<td class="code">${stock.stock_id}</td>'
    '<td class="name">${stock.name}</td>'
    '<td class="industry">${stock.industry}</td>'
    '<td>${badges}${newsHtml}</td>'
)

_CARD_HTML_FN_ARTIFACT = f"""
function cardHtml(stock) {{
  const badges = stock.signals.map(sig => {{
    const cat = codeCategory(sig.code);
    const style = badgeStyle(cat);
    return `<span class="badge" style="${{style}}">${{sig.detail}}</span>`;
  }}).join('');
  const badgesHtml = badges ? `<div class="stock-card-badges">${{badges}}</div>` : '';
  const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join('');
  const newsHtml = news ? `<div class="news">${{news}}</div>` : '';
  const grid = {_CARD_STATS_JS}.map(([label, key, suffix]) =>
    `<div class="mini-stat"><p class="label">${{label}}</p><p class="value">${{fmt(stock[key], suffix)}}</p></div>`
  ).join('');
  return `<div class="stock-card">
    <div class="stock-card-head"><span class="code">${{stock.stock_id}}</span><span class="name">${{stock.name}}</span><span class="industry">${{stock.industry}}</span></div>
    ${{badgesHtml}}
    <div class="mini-grid">${{grid}}</div>
    ${{newsHtml}}
  </div>`;
}}
"""


def build_artifact_html(run_date: str, alerts: list[dict], universe: list[dict], news_map: dict | None = None,
                         snapshots: list[dict] | None = None) -> str:
    """Standalone page matching the published Claude Artifact's design (red=偏多/rise, green=偏空/fall per TWSE convention). The scheduled task reads this file's content and republishes it to the same artifact URL each trading day."""
    narrative = build_market_narrative(alerts, universe, len(universe))
    payload = _build_unified_payload(alerts, universe, news_map, snapshots)
    triggered_count = len({a["stock_id"] for a in alerts})
    weekday = "日一二三四五六"[__import__("datetime").date.fromisoformat(run_date).isoweekday() % 7]

    return f"""<title>台股訊號板</title>
<meta name="description" content="台灣50與中型100成分股每日技術指標監測,收盤後自動更新">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --bg: #f3f2ee; --paper: #fbfaf7; --ink: #1d2027; --ink-soft: #55585f; --ink-faint: #8b8e94;
  --line: #dedbd2; --line-strong: #c7c3b6; --accent: #2b4c59; --accent-soft: #e3ebec;
  --rise: #b23a34; --rise-soft: #f5e4e2; --fall: #2f6b45; --fall-soft: #e2ecdf;
  --warn: #a3701f; --warn-soft: #f4e9d6; --info: #2f5f82; --info-soft: #e3edf3;
  --vol: #5f4f87; --vol-soft: #e9e4f2; --shadow: 0 1px 2px rgba(29,32,39,0.06), 0 8px 20px rgba(29,32,39,0.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #14161a; --paper: #1c1f24; --ink: #ece9e2; --ink-soft: #a9acb3; --ink-faint: #71747b;
    --line: #33363d; --line-strong: #454852; --accent: #8fb8c7; --accent-soft: #223338;
    --rise: #e08078; --rise-soft: #3a2523; --fall: #85c397; --fall-soft: #223a29;
    --warn: #e0b263; --warn-soft: #3a2f1a; --info: #8dbde0; --info-soft: #1f313e;
    --vol: #bba8e0; --vol-soft: #2e2740; --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.35);
  }}
}}
:root[data-theme="dark"] {{
  --bg: #14161a; --paper: #1c1f24; --ink: #ece9e2; --ink-soft: #a9acb3; --ink-faint: #71747b;
  --line: #33363d; --line-strong: #454852; --accent: #8fb8c7; --accent-soft: #223338;
  --rise: #e08078; --rise-soft: #3a2523; --fall: #85c397; --fall-soft: #223a29;
  --warn: #e0b263; --warn-soft: #3a2f1a; --info: #8dbde0; --info-soft: #1f313e;
  --vol: #bba8e0; --vol-soft: #2e2740; --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.35);
}}
* {{ box-sizing: border-box; }}
html, body {{ background: var(--bg); }}
body {{ margin: 0; padding: 28px 20px 48px; background: var(--bg); color: var(--ink);
  font-family: "IBM Plex Sans", "PingFang TC", "Noto Sans TC", sans-serif; font-variant-numeric: tabular-nums; }}
.wrap {{ max-width: 880px; margin: 0 auto; }}
.masthead {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 4px; }}
.masthead h1 {{ font-family: "Source Serif 4", Georgia, serif; font-weight: 600; font-size: clamp(26px, 4vw, 32px); margin: 0; letter-spacing: -0.01em; }}
.masthead .date {{ font-family: "IBM Plex Mono", monospace; font-size: 13px; color: var(--ink-faint); white-space: nowrap; }}
.subhead {{ color: var(--ink-soft); font-size: 14px; margin: 0 0 20px; }}
.narrative {{ background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px;
  line-height: 1.75; font-size: 14.5px; color: var(--ink); margin-bottom: 20px; box-shadow: var(--shadow); }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 18px; }}
.stat {{ background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }}
.stat .label {{ font-size: 12px; color: var(--ink-faint); margin: 0 0 6px; letter-spacing: 0.02em; }}
.stat .value {{ font-family: "IBM Plex Mono", monospace; font-size: 26px; font-weight: 500; margin: 0; line-height: 1; }}
.stat .value.rise {{ color: var(--rise); }}
.stat .value.fall {{ color: var(--fall); }}
.search {{ display: flex; gap: 8px; margin-bottom: 16px; }}
.search input {{ flex: 1; padding: 9px 14px; border-radius: 8px; border: 1px solid var(--line-strong); background: var(--paper); color: var(--ink); font-size: 14px; font-family: inherit; }}
.search button {{ font-family: inherit; font-size: 13px; padding: 7px 14px; border-radius: 8px; border: 1px solid var(--line-strong); background: var(--paper); color: var(--ink-soft); cursor: pointer; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
.filters button {{ font-family: inherit; font-size: 13px; padding: 7px 14px; border-radius: 999px;
  border: 1px solid var(--line-strong); background: var(--paper); color: var(--ink); cursor: pointer; transition: border-color .12s, background .12s; }}
.filters button:hover {{ border-color: var(--accent); }}
.filters button.active {{ background: var(--accent); border-color: var(--accent); color: var(--paper); }}
.table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; background: var(--paper); box-shadow: var(--shadow); }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; min-width: 560px; }}
thead th {{ text-align: left; padding: 10px 14px; color: var(--ink-faint); font-weight: 500; font-size: 12px;
  letter-spacing: 0.03em; border-bottom: 1px solid var(--line-strong); background: var(--paper); position: sticky; top: 0; }}
tbody tr {{ border-bottom: 1px solid var(--line); }}
tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: var(--bg); }}
td {{ padding: 9px 14px; vertical-align: top; }}
td.code {{ font-family: "IBM Plex Mono", monospace; font-weight: 500; white-space: nowrap; }}
td.name {{ white-space: nowrap; }}
td.industry {{ color: var(--ink-soft); white-space: nowrap; font-size: 12.5px; }}
.badge {{ display: inline-block; border-radius: 6px; padding: 3px 9px; font-size: 12px; margin: 2px 5px 2px 0; white-space: nowrap; font-family: "IBM Plex Mono", monospace; }}
.news {{ margin-top: 5px; font-size: 12px; max-width: 280px; }}
.news a {{ color: var(--accent); text-decoration: none; display: block; margin: 2px 0; white-space: normal; }}
.news a:hover {{ text-decoration: underline; }}
.cards {{ display: flex; flex-direction: column; gap: 14px; }}
.stock-card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 18px; box-shadow: var(--shadow); }}
.stock-card-head {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }}
.stock-card-head .code {{ font-family: "IBM Plex Mono", monospace; font-weight: 500; font-size: 17px; }}
.stock-card-head .name {{ font-size: 17px; }}
.stock-card-head .industry {{ font-size: 12px; color: var(--ink-faint); }}
.stock-card-badges {{ margin-bottom: 12px; }}
.mini-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 10px; }}
.mini-stat {{ background: var(--bg); border-radius: 8px; padding: 9px 11px; }}
.mini-stat .label {{ font-size: 11px; color: var(--ink-faint); margin: 0 0 3px; }}
.mini-stat .value {{ font-family: "IBM Plex Mono", monospace; font-size: 15px; font-weight: 500; margin: 0; }}
#empty-msg {{ display: none; color: var(--ink-faint); font-size: 13px; padding: 20px; text-align: center; }}
@media (max-width: 560px) {{ .mini-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 14px; font-size: 12px; color: var(--ink-faint); }}
.legend span {{ display: inline-flex; align-items: center; gap: 5px; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
footer {{ margin-top: 28px; font-size: 12px; color: var(--ink-faint); border-top: 1px solid var(--line); padding-top: 14px; }}
@media (max-width: 560px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} body {{ padding: 20px 14px 40px; }} }}
</style>

<div class="wrap">
  <div class="masthead">
    <h1>台股訊號板</h1>
    <span class="date">{run_date}(週{weekday})</span>
  </div>
  <p class="subhead">台灣50 + 中型100 成分股 · 每個交易日收盤後自動更新</p>
  <div class="narrative">{narrative}</div>
  <div class="stats">
    <div class="stat"><p class="label">監測檔數</p><p class="value">{len(universe)}</p></div>
    <div class="stat"><p class="label">觸發訊號</p><p class="value">{triggered_count}</p></div>
    <div class="stat"><p class="label">偏多</p><p class="value rise">{len({a["stock_id"] for a in alerts if a["signal"] in BULLISH_SIGNALS})}</p></div>
    <div class="stat"><p class="label">偏空</p><p class="value fall">{len({a["stock_id"] for a in alerts if a["signal"] in BEARISH_SIGNALS})}</p></div>
  </div>

  <div class="search">
    <input type="text" id="search-input" placeholder="搜尋代號或名稱(例如 2330 或 台積電),查任一檔目前指標數值">
    <button type="button" id="search-clear">清除</button>
  </div>

  <div id="filters" class="filters"></div>
  <div id="table-wrap" class="table-wrap">
    <table>
      <thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>觸發訊號</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div id="cards" class="cards" style="display:none"></div>
  <p id="empty-msg"></p>
  <div class="legend">
    <span><i class="dot" style="background:var(--rise)"></i>偏多(新高/黃金交叉/突破上軌)</span>
    <span><i class="dot" style="background:var(--fall)"></i>偏空(新低/死亡交叉/跌破下軌)</span>
    <span><i class="dot" style="background:var(--warn)"></i>RSI超買</span>
    <span><i class="dot" style="background:var(--info)"></i>RSI超賣</span>
    <span><i class="dot" style="background:var(--vol)"></i>成交量異常</span>
  </div>
  <footer>資料來源:FinMind · 指標:MA交叉/RSI/MACD/布林通道/成交量/新高新低,任一觸發即列入 · 搜尋可查全部{len(universe)}檔目前數值 · 僅供個人參考,非投資建議</footer>
</div>

<script>
const STOCKS = {json.dumps(payload, ensure_ascii=False)};
const CATS = {json.dumps(ARTIFACT_CATEGORIES, ensure_ascii=False)};
{_SEARCH_SCRIPT}
function codeCategory(code) {{ for (const key in CATS) {{ if (CATS[key].codes.includes(code)) return key; }} return null; }}
function stockCats(stock) {{ const s = new Set(); stock.signals.forEach(sig => {{ const c = codeCategory(sig.code); if (c) s.add(c); }}); return s; }}
function badgeStyle(cat) {{
  return cat ? `background:var(${{CATS[cat].varBg}});color:var(${{CATS[cat].varText}})` : "background:var(--bg);color:var(--ink-soft)";
}}
{_CARD_HTML_FN_ARTIFACT}

let activeFilter = "all";
let searchQuery = "";

function renderFilters() {{
  const el = document.getElementById("filters");
  if (searchQuery.trim()) {{ el.style.display = "none"; return; }}
  el.style.display = "flex";
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  const counts = {{ all: triggered.length }};
  Object.keys(CATS).forEach(k => {{ counts[k] = triggered.filter(a => stockCats(a).has(k)).length; }});
  el.innerHTML = "";
  const items = [["all", "全部"]].concat(Object.keys(CATS).map(k => [k, CATS[k].label]));
  items.forEach(([key, label]) => {{
    const btn = document.createElement("button"); btn.type = "button";
    btn.textContent = `${{label}} (${{counts[key]}})`;
    btn.className = key === activeFilter ? "active" : "";
    btn.addEventListener("click", () => {{ activeFilter = key; render(); }});
    el.appendChild(btn);
  }});
}}

function getVisible() {{
  if (searchQuery.trim()) {{
    return STOCKS.filter(s => matchesSearch(s, searchQuery));
  }}
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  return activeFilter === "all" ? triggered : triggered.filter(s => stockCats(s).has(activeFilter));
}}

function render() {{
  renderFilters();
  const visible = getVisible();
  const searching = searchQuery.trim().length > 0;
  const emptyMsg = document.getElementById("empty-msg");
  const tableWrap = document.getElementById("table-wrap");
  const cardsWrap = document.getElementById("cards");

  if (!visible.length) {{
    emptyMsg.style.display = "block";
    emptyMsg.textContent = searching
      ? `查無「${{searchQuery}}」相關股票(僅收錄台灣50+中型100共{len(universe)}檔)`
      : "今日無觸發訊號。";
  }} else {{
    emptyMsg.style.display = "none";
  }}

  tableWrap.style.display = searching ? "none" : "block";
  cardsWrap.style.display = searching ? "flex" : "none";

  if (searching) {{
    cardsWrap.innerHTML = visible.map(cardHtml).join("");
    return;
  }}

  const rows = document.getElementById("rows"); rows.innerHTML = "";
  visible.forEach(stock => {{
    const tr = document.createElement("tr");
    const badges = stock.signals.map(sig => `<span class="badge" style="${{badgeStyle(codeCategory(sig.code))}}">${{sig.detail}}</span>`).join("");
    const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join("");
    const newsHtml = news ? `<div class="news">${{news}}</div>` : "";
    tr.innerHTML = `{_ROW_HTML_ARTIFACT}`;
    rows.appendChild(tr);
  }});
}}

document.getElementById("search-input").addEventListener("input", (e) => {{ searchQuery = e.target.value; render(); }});
document.getElementById("search-clear").addEventListener("click", () => {{ searchQuery = ""; document.getElementById("search-input").value = ""; render(); }});
render();
</script>
"""


def write_artifact_source(report_dir: str, run_date: str, alerts: list[dict], universe: list[dict],
                           news_map: dict | None = None, snapshots: list[dict] | None = None) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{run_date}_artifact.html"
    path.write_text(build_artifact_html(run_date, alerts, universe, news_map, snapshots), encoding="utf-8")
    return str(path)


def build_summary_text(run_date: str, alerts: list[dict], fetch_stats: dict, universe: list[dict]) -> str:
    by_stock = _group_by_stock(alerts)
    groups = _group_by_signal(alerts)

    lines = [
        f"📊 台股監測報表 {run_date}",
        f"資料更新:成功{fetch_stats['ok']} 略過{fetch_stats['skipped']} 失敗{fetch_stats['failed']} / 共{fetch_stats['total']}檔",
        "",
        build_market_narrative(alerts, universe, len(universe)),
    ]
    if not by_stock:
        return "\n".join(lines)

    lines.append("")
    lines.append("【依訊號類型】")
    for code in SIGNAL_ORDER:
        items = groups.get(code, [])
        if not items:
            continue
        names = "、".join(f"{a['stock_id']}{a['stock_name']}" for a in items)
        lines.append(f"▪ {SIGNAL_SECTION_TITLE[code]}({len(items)}):{names}")

    lines.append("")
    lines.append("【依個股彙總】")
    for sid, v in by_stock.items():
        lines.append(f"• {sid} {v['name']}:{'、'.join(v['signals'])}")
    return "\n".join(lines)
