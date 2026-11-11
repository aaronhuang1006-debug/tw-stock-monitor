import csv
import json
from collections import Counter
from pathlib import Path

from . import trend_ui

WEEKLY_BULLISH = ["wma_golden_cross", "w_macd_golden_cross", "w_bb_breakout_upper", "w_new_high"]
WEEKLY_BEARISH = ["wma_death_cross", "w_macd_death_cross", "w_bb_breakout_lower", "w_new_low"]
DAILY_BULLISH = ["ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high"]
DAILY_BEARISH = ["ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low"]
WEEKLY_CODES = WEEKLY_BULLISH + WEEKLY_BEARISH + ["w_rsi_overbought", "w_rsi_oversold", "w_volume_spike"]
# Close crossing its own 5-day / 20-day line. Kept out of 偏多/偏空 so those counts stay comparable with
# earlier days; the 5-day ones fire on ~25% of the universe a day, so they stay off the Telegram lists.
MA5_POS = ["close_above_ma5", "close_below_ma5"]
MA20_POS = ["close_above_ma20", "close_below_ma20"]
MA_POS_CODES = MA20_POS + MA5_POS
NOISY_CODES = set(MA5_POS)  # shown on the board under their own filter; not counted as "觸發", not listed in Telegram

SIGNAL_ORDER = (
    WEEKLY_BULLISH + DAILY_BULLISH + WEEKLY_BEARISH + DAILY_BEARISH
    + ["w_rsi_overbought", "rsi_overbought", "w_rsi_oversold", "rsi_oversold", "w_volume_spike", "volume_spike"]
    + MA_POS_CODES
)

SIGNAL_SECTION_TITLE = {
    "wma_golden_cross": "週線黃金交叉",
    "wma_death_cross": "週線死亡交叉",
    "w_macd_golden_cross": "週MACD金叉",
    "w_macd_death_cross": "週MACD死叉",
    "w_bb_breakout_upper": "週線突破布林上軌",
    "w_bb_breakout_lower": "週線跌破布林下軌",
    "w_new_high": "創60週新高",
    "w_new_low": "創60週新低",
    "w_rsi_overbought": "週RSI超買(中期過熱)",
    "w_rsi_oversold": "週RSI超賣(中期超跌)",
    "w_volume_spike": "週成交量異常放大",
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
    "close_above_ma20": "站上月線(20日)",
    "close_below_ma20": "跌破月線(20日)",
    "close_above_ma5": "站上5日線",
    "close_below_ma5": "跌破5日線",
}

BULLISH_SIGNALS = set(WEEKLY_BULLISH + DAILY_BULLISH)
BEARISH_SIGNALS = set(WEEKLY_BEARISH + DAILY_BEARISH)

FILTER_CATEGORIES = {
    "bull": {"label": "偏多", "codes": WEEKLY_BULLISH + DAILY_BULLISH, "bg": "#E1F5EE", "text": "#04342C"},
    "bear": {"label": "偏空", "codes": WEEKLY_BEARISH + DAILY_BEARISH, "bg": "#FAECE7", "text": "#4A1B0C"},
    "wbull": {"label": "週線偏多", "codes": WEEKLY_BULLISH, "bg": "#E1F5EE", "text": "#04342C"},
    "wbear": {"label": "週線偏空", "codes": WEEKLY_BEARISH, "bg": "#FAECE7", "text": "#4A1B0C"},
    "overbought": {"label": "RSI超買", "codes": ["rsi_overbought", "w_rsi_overbought"], "bg": "#FAEEDA", "text": "#412402"},
    "oversold": {"label": "RSI超賣", "codes": ["rsi_oversold", "w_rsi_oversold"], "bg": "#E6F1FB", "text": "#042C53"},
    "volume": {"label": "成交量異常", "codes": ["volume_spike", "w_volume_spike"], "bg": "#EEEDFE", "text": "#26215C"},
    "ma20": {"label": "月線(20日)", "codes": MA20_POS, "bg": "#E3EBEC", "text": "#1F3A44"},
    "ma5": {"label": "5日線", "codes": MA5_POS, "bg": "#E3EBEC", "text": "#1F3A44"},
}

ARTIFACT_CATEGORIES = {
    "bull": {"label": "偏多", "codes": WEEKLY_BULLISH + DAILY_BULLISH, "varBg": "--rise-soft", "varText": "--rise"},
    "bear": {"label": "偏空", "codes": WEEKLY_BEARISH + DAILY_BEARISH, "varBg": "--fall-soft", "varText": "--fall"},
    "wbull": {"label": "週線偏多", "codes": WEEKLY_BULLISH, "varBg": "--rise-soft", "varText": "--rise"},
    "wbear": {"label": "週線偏空", "codes": WEEKLY_BEARISH, "varBg": "--fall-soft", "varText": "--fall"},
    "overbought": {"label": "RSI超買", "codes": ["rsi_overbought", "w_rsi_overbought"], "varBg": "--warn-soft", "varText": "--warn"},
    "oversold": {"label": "RSI超賣", "codes": ["rsi_oversold", "w_rsi_oversold"], "varBg": "--info-soft", "varText": "--info"},
    "volume": {"label": "成交量異常", "codes": ["volume_spike", "w_volume_spike"], "varBg": "--vol-soft", "varText": "--vol"},
    "ma20": {"label": "月線(20日)", "codes": MA20_POS, "varBg": "--accent-soft", "varText": "--accent"},
    "ma5": {"label": "5日線", "codes": MA5_POS, "varBg": "--accent-soft", "varText": "--accent"},
}


TREND_METRICS = [
    {"key": "all", "label": "觸發檔數", "series": [{"name": "觸發", "codes": [c for c in SIGNAL_ORDER if c not in MA_POS_CODES], "color": "--accent"}]},
    {"key": "bs", "label": "偏多 vs 偏空", "series": [
        {"name": "偏多", "codes": WEEKLY_BULLISH + DAILY_BULLISH, "color": "--rise"},
        {"name": "偏空", "codes": WEEKLY_BEARISH + DAILY_BEARISH, "color": "--fall", "dash": "6 4"}]},
    {"key": "rsi", "label": "RSI 超買 vs 超賣", "series": [
        {"name": "超買", "codes": ["rsi_overbought", "w_rsi_overbought"], "color": "--warn"},
        {"name": "超賣", "codes": ["rsi_oversold", "w_rsi_oversold"], "color": "--info", "dash": "6 4"}]},
    {"key": "wk", "label": "週線偏多 vs 偏空", "weekly": True,
     "note": "週線訊號只在週收盤判斷(遇週五休市則在下週第一個交易日),所以這張圖以週為單位。",
     "series": [
        {"name": "週偏多", "codes": WEEKLY_BULLISH, "color": "--rise"},
        {"name": "週偏空", "codes": WEEKLY_BEARISH, "color": "--fall", "dash": "6 4"}]},
]


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
    by_stock = _group_by_stock([a for a in alerts if a["signal"] not in NOISY_CODES])

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

    weekly_parts = []
    for code in [c for c in SIGNAL_ORDER if c in WEEKLY_CODES]:
        items = [a for a in alerts if a["signal"] == code]
        if items:
            names = "、".join(a["stock_name"] for a in items[:5]) + ("等" if len(items) > 5 else "")
            weekly_parts.append(f"{SIGNAL_SECTION_TITLE[code]}{len(items)}檔({names})")
    if weekly_parts:
        lines.append("週線(週收盤判斷)出現" + "、".join(weekly_parts) + "。")

    if overbought_ids or oversold_ids:
        lines.append(f"RSI超買{len(overbought_ids)}檔、超賣{len(oversold_ids)}檔。")

    ma_counts = {c: len({a["stock_id"] for a in alerts if a["signal"] == c}) for c in MA_POS_CODES}
    if any(ma_counts.values()):
        lines.append(
            f"收盤站上月線{ma_counts['close_above_ma20']}檔、跌破月線{ma_counts['close_below_ma20']}檔;"
            f"站上5日線{ma_counts['close_above_ma5']}檔、跌破5日線{ma_counts['close_below_ma5']}檔。"
        )
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
    ("收盤", "close", ""), ("MA5", "ma5", ""), ("MA20", "ma20", ""), ("MA60", "ma60", ""),
    ("RSI", "rsi", ""), ("MACD", "macd", ""), ("MACD訊號", "macd_signal", ""),
    ("布林上軌", "bb_upper", ""), ("布林下軌", "bb_lower", ""), ("量比", "vol_ratio", "x"),
    ("週MA5", "wma5", ""), ("週MA20", "wma20", ""), ("週RSI", "wrsi", ""), ("週MACD", "wmacd", ""),
    ("週MACD訊號", "wmacd_signal", ""), ("週布林上軌", "wbb_upper", ""), ("週布林下軌", "wbb_lower", ""),
    ("週量比", "wvol_ratio", "x"),
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
.mini-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 8px; }}
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
  stock.signals.forEach(sig => {{ for (const k in CATS) {{ if (CATS[k].codes.includes(sig.code)) s.add(k); }} }});
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
    const style = sigStyle(sig.code);
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
    ${{stockChartHtml(stock)}}
  </div>`;
}}
"""


# ---- Weekly MA cross panel (artifact / Pages only). Plain strings, spliced into the f-string page. ----
# Weekly crosses are only judged on the weekly close, so on every other day they vanish from the
# signal table. This panel reads HIST and keeps showing the latest weekly close until the next one.
WEEKLY_CROSS_CSS = """
.wx { background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px 14px; margin-bottom: 18px; box-shadow: var(--shadow); }
.wx[hidden] { display: none; }
.wx-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.wx-head h2 { font-family: "Source Serif 4", Georgia, serif; font-size: 18px; font-weight: 600; margin: 0; }
.wx-when { font-family: "IBM Plex Mono", monospace; font-size: 12.5px; color: var(--ink-soft); }
.wx-when.today { color: var(--accent); font-weight: 500; }
.wx-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.wx-col { min-width: 0; border-radius: 8px; padding: 12px 12px 10px; border-left: 4px solid; }
.wx-col.gold { background: var(--rise-soft); border-color: var(--rise); }
.wx-col.death { background: var(--fall-soft); border-color: var(--fall); }
.wx-col h3 { margin: 0 0 8px; font-size: 14px; font-weight: 600; display: flex; align-items: baseline; gap: 8px; }
.wx-col.gold h3 { color: var(--rise); }
.wx-col.death h3 { color: var(--fall); }
.wx-col h3 b { font-family: "IBM Plex Mono", monospace; font-size: 22px; font-weight: 500; line-height: 1; }
.wx-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.wx-chip { font-family: inherit; font-size: 12.5px; padding: 4px 9px; border-radius: 6px; border: 0; cursor: pointer; color: var(--paper); font-weight: 500; }
.wx-chip .c { font-family: "IBM Plex Mono", monospace; opacity: .85; margin-right: 5px; }
.wx-col.gold .wx-chip { background: var(--rise); }
.wx-col.death .wx-chip { background: var(--fall); }
.wx-chip:hover { filter: brightness(1.08); }
.wx-chip:focus-visible, .wx-prev summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wx-none { font-size: 12.5px; color: var(--ink-faint); margin: 0; }
.wx-prev { margin-top: 10px; font-size: 12.5px; color: var(--ink-soft); }
.wx-prev summary { cursor: pointer; width: fit-content; }
.wx-prev-row { display: grid; grid-template-columns: 52px 1fr; gap: 4px 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
.wx-prev-row:last-child { border-bottom: none; }
.wx-prev-row .d { font-family: "IBM Plex Mono", monospace; color: var(--ink-faint); }
.wx-prev-row .g { color: var(--rise); }
.wx-prev-row .x { color: var(--fall); }
.wx-prev-row div { min-width: 0; }
.wx-note { font-size: 12px; color: var(--ink-faint); margin: 8px 0 0; }
@media (max-width: 560px) { .wx-cols { grid-template-columns: 1fr; } }
"""

WEEKLY_CROSS_HTML = """
  <section id="wx" class="wx" aria-label="週線交叉">
    <div class="wx-head"><h2>週線交叉</h2><span id="wx-when" class="wx-when"></span></div>
    <div class="wx-cols">
      <div class="wx-col gold"><h3>黃金交叉 <b id="wx-g-n">0</b></h3><div id="wx-g" class="wx-chips"></div></div>
      <div class="wx-col death"><h3>死亡交叉 <b id="wx-d-n">0</b></h3><div id="wx-d" class="wx-chips"></div></div>
    </div>
    <details class="wx-prev"><summary>前幾週的週線交叉</summary><div id="wx-prev"></div></details>
    <p class="wx-note">5週線與20週線交叉,只在週收盤判斷。下一次週收盤之前,這裡都保留最近一週的結果;點股票可查看指標與走勢。</p>
  </section>
"""

WEEKLY_CROSS_JS = """
const WX_SOLID = { wma_golden_cross: "--rise", wma_death_cross: "--fall" };
const MA_SOFT = { close_above_ma20: "rise", close_below_ma20: "fall", close_above_ma5: "rise", close_below_ma5: "fall" };
function sigStyle(code) {
  if (WX_SOLID[code]) return `background:var(${WX_SOLID[code]});color:var(--paper);font-weight:600`;
  if (MA_SOFT[code]) return `background:var(--${MA_SOFT[code]}-soft);color:var(--${MA_SOFT[code]})`;
  return badgeStyle(codeCategory(code));
}
function renderWeeklyCross() {
  const sec = document.getElementById("wx");
  const codes = HIST.codes || [], days = HIST.days || [];
  const gi = codes.indexOf("wma_golden_cross"), di = codes.indexOf("wma_death_cross");
  const wIdx = new Set(codes.map((c, i) => (c.startsWith("w_") || c.startsWith("wma_")) ? i : -1).filter(i => i >= 0));
  const order = {}, names = {};
  STOCKS.forEach((s, i) => { order[s.stock_id] = i; names[s.stock_id] = s.name; });
  const weekDays = days.filter(d => Object.values(d.s || {}).some(v => v.some(i => wIdx.has(i))));
  if (gi < 0 || di < 0 || !weekDays.length) { sec.dataset.empty = "1"; sec.hidden = true; return; }
  const pick = (d, idx) => Object.keys(d.s).filter(id => d.s[id].includes(idx)).sort((a, b) => (order[a] ?? 1e9) - (order[b] ?? 1e9));
  const wd = ds => "日一二三四五六"[new Date(ds + "T00:00:00").getDay()];
  const md = ds => ds.slice(5).replace("-", "/");
  const last = weekDays[weekDays.length - 1];
  const today = days.length && days[days.length - 1].d === last.d;
  const when = document.getElementById("wx-when");
  when.textContent = today ? `今天週收盤判斷 · ${last.d}` : `最近一次週收盤:${last.d}(週${wd(last.d)})`;
  when.className = "wx-when" + (today ? " today" : "");
  const fill = (id, list) => {
    document.getElementById(id + "-n").textContent = list.length;
    const el = document.getElementById(id);
    el.innerHTML = list.length ? "" : '<p class="wx-none">這週沒有</p>';
    list.forEach(sid => {
      const b = document.createElement("button"); b.type = "button"; b.className = "wx-chip";
      b.innerHTML = `<span class="c">${sid}</span>${names[sid] || ""}`;
      b.addEventListener("click", () => {
        navTo({ q: sid, f: "all" }, true);
      });
      el.appendChild(b);
    });
  };
  fill("wx-g", pick(last, gi));
  fill("wx-d", pick(last, di));
  const nm = list => list.length ? list.map(id => names[id] || id).join("、") : "—";
  const prev = weekDays.slice(0, -1).slice(-6).reverse();
  document.getElementById("wx-prev").innerHTML = prev.length ? prev.map(d =>
    `<div class="wx-prev-row"><span class="d">${md(d.d)}</span><div><span class="g">金叉 ${pick(d, gi).length}:</span>${nm(pick(d, gi))}<br><span class="x">死叉 ${pick(d, di).length}:</span>${nm(pick(d, di))}</div></div>`
  ).join("") : '<p class="wx-none">還沒有更早的紀錄</p>';
}
"""


# ---- In-page navigation: 上一頁 / 回主畫面 (artifact / Pages only) ----
# The page is one view whose state is (search text, active filter, scroll). A small stack of those
# states backs the two buttons; browser history is left alone because the page runs inside a frame.
NAV_CSS = """
.navbar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; display: flex; align-items: center; gap: 8px;
  margin: -8px 0 12px; padding: 8px 0; background: var(--bg); border-bottom: 1px solid var(--line); }
.navbar[hidden] { display: none; }
.navbar button { font-family: inherit; font-size: 13px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--line-strong);
  background: var(--paper); color: var(--ink); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.navbar button:hover:not(:disabled) { border-color: var(--accent); }
.navbar button:disabled { opacity: .45; cursor: default; }
.navbar button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.navbar .where { margin-left: auto; font-size: 12.5px; color: var(--ink-soft); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
"""

NAV_HTML = """
  <nav id="navbar" class="navbar" aria-label="頁面導覽" hidden>
    <button type="button" id="nav-back"><span aria-hidden="true">‹</span>上一頁</button>
    <button type="button" id="nav-home"><span aria-hidden="true">⌂</span>回主畫面</button>
    <span id="nav-where" class="where"></span>
  </nav>
"""

NAV_JS = """
const NAV_STACK = [];
function navState() { return { q: searchQuery, f: activeFilter, y: window.scrollY }; }
function navApply(st, scroll) {
  searchQuery = st.q; activeFilter = st.f;
  document.getElementById("search-input").value = st.q;
  render();
  if (scroll === "top") window.scrollTo(0, 0);
  else if (typeof scroll === "number") window.scrollTo(0, scroll);
}
function navTo(next, toTop) {
  const cur = navState();
  if (cur.q === next.q && cur.f === next.f) return;
  NAV_STACK.push(cur);
  navApply({ q: next.q, f: next.f }, toTop ? "top" : undefined);
}
function navBack() {
  if (!NAV_STACK.length) return;
  const st = NAV_STACK.pop();
  navApply(st, st.y);
}
function navHome() {
  NAV_STACK.length = 0;
  navApply({ q: "", f: "all" }, "top");
}
function renderNav() {
  const home = !searchQuery.trim() && activeFilter === "all";
  const bar = document.getElementById("navbar");
  bar.hidden = home && !NAV_STACK.length;
  document.getElementById("nav-back").disabled = !NAV_STACK.length;
  document.getElementById("nav-home").disabled = home;
  const where = document.getElementById("nav-where");
  if (searchQuery.trim()) where.textContent = `搜尋:${searchQuery.trim()}`;
  else if (activeFilter !== "all") where.textContent = `篩選:${CATS[activeFilter] ? CATS[activeFilter].label : activeFilter}`;
  else where.textContent = "主畫面";
}
document.getElementById("nav-back").addEventListener("click", navBack);
document.getElementById("nav-home").addEventListener("click", navHome);
"""


def build_artifact_html(run_date: str, alerts: list[dict], universe: list[dict], news_map: dict | None = None,
                         snapshots: list[dict] | None = None, history: dict | None = None,
                         series: dict | None = None) -> str:
    """Standalone page matching the published Claude Artifact's design (red=偏多/rise, green=偏空/fall per TWSE convention). The scheduled task reads this file's content and republishes it to the same artifact URL each trading day."""
    narrative = build_market_narrative(alerts, universe, len(universe))
    payload = _build_unified_payload(alerts, universe, news_map, snapshots)
    triggered_count = len({a["stock_id"] for a in alerts if a["signal"] not in NOISY_CODES})
    hist_json = json.dumps(history or {"codes": [], "days": []}, ensure_ascii=False, separators=(",", ":"))
    series_json = json.dumps(series or {"dates": [], "v": {}}, ensure_ascii=False, separators=(",", ":"))
    siglabel_json = json.dumps(SIGNAL_SECTION_TITLE, ensure_ascii=False)
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
.mini-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 10px; }}
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
{trend_ui.TREND_CSS}
{WEEKLY_CROSS_CSS}
{NAV_CSS}
</style>

<div class="wrap">
{NAV_HTML}
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
{WEEKLY_CROSS_HTML}
{trend_ui.TREND_HTML}
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
    <span><i class="dot" style="background:var(--rise)"></i>偏多(新高/黃金交叉/MACD金叉/突破上軌,日線與週線)</span>
    <span><i class="dot" style="background:var(--fall)"></i>偏空(新低/死亡交叉/MACD死叉/跌破下軌,日線與週線)</span>
    <span><i class="dot" style="background:var(--warn)"></i>RSI超買</span>
    <span><i class="dot" style="background:var(--info)"></i>RSI超賣</span>
    <span><i class="dot" style="background:var(--vol)"></i>成交量異常</span>
    <span><i class="dot" style="background:var(--accent)"></i>收盤站上/跌破5日線、月線(紅=站上、綠=跌破;5日線另列,不計入觸發檔數)</span>
  </div>
  <footer>資料來源:FinMind · 指標:MA交叉/收盤穿越5日線與月線/RSI/MACD/布林通道/成交量/新高新低,日線與週線各算一套(週線用5週vs20週、60週新高低,只在週收盤判斷;卡片上週線數值為含本週的暫時值),任一觸發即列入 · 搜尋可查全部{len(universe)}檔目前數值 · 僅供個人參考,非投資建議</footer>
</div>

<script>
const STOCKS = {json.dumps(payload, ensure_ascii=False)};
const CATS = {json.dumps(ARTIFACT_CATEGORIES, ensure_ascii=False)};
const HIST = {hist_json};
const SER = {series_json};
const SIGLABEL = {siglabel_json};
const TREND_METRICS = {json.dumps(TREND_METRICS, ensure_ascii=False)};
const BULL_CODES = {json.dumps(sorted(BULLISH_SIGNALS))};
const BEAR_CODES = {json.dumps(sorted(BEARISH_SIGNALS))};
const NOISY = new Set({json.dumps(sorted(NOISY_CODES))});
const isCore = s => s.signals.some(g => !NOISY.has(g.code));
{trend_ui.TREND_JS}
{_SEARCH_SCRIPT}
function codeCategory(code) {{ for (const key in CATS) {{ if (CATS[key].codes.includes(code)) return key; }} return null; }}
function stockCats(stock) {{ const s = new Set(); stock.signals.forEach(sig => {{ for (const k in CATS) {{ if (CATS[k].codes.includes(sig.code)) s.add(k); }} }}); return s; }}
function badgeStyle(cat) {{
  return cat ? `background:var(${{CATS[cat].varBg}});color:var(${{CATS[cat].varText}})` : "background:var(--bg);color:var(--ink-soft)";
}}
{_CARD_HTML_FN_ARTIFACT}
{WEEKLY_CROSS_JS}

let activeFilter = "all";
let searchQuery = "";

function renderFilters() {{
  const el = document.getElementById("filters");
  if (searchQuery.trim()) {{ el.style.display = "none"; return; }}
  el.style.display = "flex";
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  const counts = {{ all: STOCKS.filter(isCore).length }};
  Object.keys(CATS).forEach(k => {{ counts[k] = triggered.filter(a => stockCats(a).has(k)).length; }});
  el.innerHTML = "";
  const items = [["all", "全部"]].concat(Object.keys(CATS).map(k => [k, CATS[k].label]));
  items.forEach(([key, label]) => {{
    const btn = document.createElement("button"); btn.type = "button";
    btn.textContent = `${{label}} (${{counts[key]}})`;
    btn.className = key === activeFilter ? "active" : "";
    btn.addEventListener("click", () => {{ navTo({{ q: "", f: key }}); }});
    el.appendChild(btn);
  }});
}}

function getVisible() {{
  if (searchQuery.trim()) {{
    return STOCKS.filter(s => matchesSearch(s, searchQuery));
  }}
  const triggered = STOCKS.filter(s => s.signals.length > 0);
  return activeFilter === "all" ? STOCKS.filter(isCore) : triggered.filter(s => stockCats(s).has(activeFilter));
}}

function render() {{
  renderFilters();
  const visible = getVisible();
  const searching = searchQuery.trim().length > 0;
  document.getElementById("trend").hidden = searching;
  document.getElementById("wx").hidden = searching || document.getElementById("wx").dataset.empty === "1";
  renderNav();
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
    const badges = stock.signals.map(sig => `<span class="badge" style="${{sigStyle(sig.code)}}">${{sig.detail}}</span>`).join("");
    const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join("");
    const newsHtml = news ? `<div class="news">${{news}}</div>` : "";
    tr.innerHTML = `{_ROW_HTML_ARTIFACT}`;
    rows.appendChild(tr);
  }});
}}

document.getElementById("search-input").addEventListener("input", (e) => {{
  if (!searchQuery.trim() && e.target.value.trim()) NAV_STACK.push(navState());
  searchQuery = e.target.value; render();
}});
document.getElementById("search-clear").addEventListener("click", () => {{ navTo({{ q: "", f: activeFilter }}); }});
{NAV_JS}
renderTrend();
renderWeeklyCross();
render();
</script>
"""


def write_artifact_source(report_dir: str, run_date: str, alerts: list[dict], universe: list[dict],
                           news_map: dict | None = None, snapshots: list[dict] | None = None,
                           history: dict | None = None, series: dict | None = None) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{run_date}_artifact.html"
    path.write_text(build_artifact_html(run_date, alerts, universe, news_map, snapshots, history, series), encoding="utf-8")
    return str(path)


def build_summary_text(run_date: str, alerts: list[dict], fetch_stats: dict, universe: list[dict]) -> str:
    listed = [a for a in alerts if a["signal"] not in NOISY_CODES]  # 5日線 crosses: counted in the narrative only
    by_stock = _group_by_stock(listed)
    groups = _group_by_signal(listed)

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
