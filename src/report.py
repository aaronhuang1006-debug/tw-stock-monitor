import csv
import html
import re
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
BIAS_POS = ["bias_pos_35", "bias_pos_25", "bias_pos_15"]
BIAS_NEG = ["bias_neg_35", "bias_neg_25", "bias_neg_15"]
BIAS_CODES = BIAS_POS + BIAS_NEG
# Groups from the 2016-2026 backtest (backtest/results): 60-day excess return vs the universe average.
# New highs / RSI overbought / upper-band breaks kept outperforming; new lows / RSI oversold / lower-band
# breaks kept underperforming; every crossover (MA, MACD, weekly MA, close vs 5/20-day line) was ~noise.
STRONG = ["w_new_high", "new_high", "w_rsi_overbought", "rsi_overbought", "w_bb_breakout_upper", "bb_breakout_upper"]
WEAK = ["w_new_low", "new_low", "w_rsi_oversold", "rsi_oversold", "w_bb_breakout_lower", "bb_breakout_lower"]
CROSS = ["wma_golden_cross", "wma_death_cross", "w_macd_golden_cross", "w_macd_death_cross",
         "ma_golden_cross", "ma_death_cross", "macd_golden_cross", "macd_death_cross"]
STRONG_SET, WEAK_SET = set(STRONG), set(WEAK)
BACKTEST = {  # numbers quoted on the board; from backtest/results/results.json (2016-01 to 2026-11, 169 stocks)
    "period": "2016–2026",
    "strong": "創新高、RSI超買、突破布林上軌之後60個交易日,平均贏同期170檔平均1.6%~4.5%",
    "weak": "創新低、RSI超賣、跌破布林下軌之後60個交易日,平均輸1.0%~3.2%",
    "cross": "均線、MACD、週線的黃金/死亡交叉,以及站上/跌破5日線、月線,之後的表現跟平均差不多(多在±0.9%內,低於來回交易成本0.585%)",
    "volume": "成交量放大2倍之後60個交易日平均贏1.0%",
    "thermo": "歷史上全市場超賣比例≥30%的37個交易日,之後60個交易日170檔平均漲14.6%(平時6.0%);但只來自約5~6次大跌,樣本很少",
}
RSI_NOTE = {
    "rsi_overbought": "近14日漲勢一面倒;回測多半續強,不是賣訊",
    "w_rsi_overbought": "近14週漲勢一面倒;回測多半續強,不是賣訊",
    "rsi_oversold": "近14日跌勢一面倒;回測多半續弱,不是買訊",
    "w_rsi_oversold": "近14週跌勢一面倒;回測多半續弱,不是買訊",
}
# Mon-Thu preview of the weekly rules on the week so far (screener.screen_weekly_provisional).
WP_BULL = ["wp_wma_golden_cross", "wp_macd_golden_cross", "wp_bb_breakout_upper", "wp_new_high", "wp_rsi_overbought"]
WP_BEAR = ["wp_wma_death_cross", "wp_macd_death_cross", "wp_bb_breakout_lower", "wp_new_low", "wp_rsi_oversold"]
WP_CODES = WP_BULL + WP_BEAR
NOISY_CODES = set(MA5_POS) | set(WP_CODES)  # board only: own filter, not in 全部/觸發 count or Telegram lists  # shown on the board under their own filter; not counted as "觸發", not listed in Telegram

SIGNAL_ORDER = STRONG + WEAK + ["w_volume_spike", "volume_spike"] + BIAS_CODES + CROSS + MA_POS_CODES + WP_CODES

SIGNAL_SECTION_TITLE = {
    "wma_golden_cross": "週線黃金交叉(參考)",
    "wma_death_cross": "週線死亡交叉(參考)",
    "w_macd_golden_cross": "週MACD金叉(參考)",
    "w_macd_death_cross": "週MACD死叉(參考)",
    "w_bb_breakout_upper": "週線突破布林上軌",
    "w_bb_breakout_lower": "週線跌破布林下軌",
    "w_new_high": "創60週新高",
    "w_new_low": "創60週新低",
    "w_rsi_overbought": "週RSI超買(近14週漲勢一面倒,回測多續強)",
    "w_rsi_oversold": "週RSI超賣(近14週跌勢一面倒,回測多續弱)",
    "w_volume_spike": "週成交量異常放大",
    "ma_golden_cross": "均線黃金交叉(參考)",
    "macd_golden_cross": "MACD金叉(參考)",
    "bb_breakout_upper": "突破布林上軌",
    "new_high": "創60日新高",
    "ma_death_cross": "均線死亡交叉(參考)",
    "macd_death_cross": "MACD死叉(參考)",
    "bb_breakout_lower": "跌破布林下軌",
    "new_low": "創60日新低",
    "rsi_overbought": "RSI超買(近14日漲勢一面倒,回測多續強)",
    "rsi_oversold": "RSI超賣(近14日跌勢一面倒,回測多續弱)",
    "volume_spike": "成交量異常放大",
    "close_above_ma20": "站上月線(20日)",
    "close_below_ma20": "跌破月線(20日)",
    "close_above_ma5": "站上5日線",
    "close_below_ma5": "跌破5日線",
    "bias_pos_35": "月線正乖離≥35%",
    "bias_pos_25": "月線正乖離25~35%",
    "bias_pos_15": "月線正乖離15~25%",
    "bias_neg_35": "月線負乖離≥35%",
    "bias_neg_25": "月線負乖離25~35%",
    "bias_neg_15": "月線負乖離15~25%",
    "wp_wma_golden_cross": "週線黃金交叉(本週暫定)",
    "wp_wma_death_cross": "週線死亡交叉(本週暫定)",
    "wp_macd_golden_cross": "週MACD金叉(本週暫定)",
    "wp_macd_death_cross": "週MACD死叉(本週暫定)",
    "wp_bb_breakout_upper": "週線突破布林上軌(本週暫定)",
    "wp_bb_breakout_lower": "週線跌破布林下軌(本週暫定)",
    "wp_new_high": "創60週新高(本週暫定)",
    "wp_new_low": "創60週新低(本週暫定)",
    "wp_rsi_overbought": "週RSI超買(本週暫定)",
    "wp_rsi_oversold": "週RSI超賣(本週暫定)",
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
    "bias": {"label": "月線乖離≥15%", "codes": BIAS_CODES, "bg": "#F4E9D6", "text": "#6B4A14"},
    "wprov": {"label": "週線(本週暫定)", "codes": WP_CODES, "bg": "#F3F2EE", "text": "#55585F"},
    "ma5": {"label": "5日線", "codes": MA5_POS, "bg": "#E3EBEC", "text": "#1F3A44"},
}

ARTIFACT_CATEGORIES = {
    "strong": {"label": "強勢趨勢", "codes": STRONG, "varBg": "--rise-soft", "varText": "--rise"},
    "weak": {"label": "弱勢趨勢", "codes": WEAK, "varBg": "--fall-soft", "varText": "--fall"},
    "overbought": {"label": "RSI超買(漲勢一面倒)", "codes": ["rsi_overbought", "w_rsi_overbought"], "varBg": "--rise-soft", "varText": "--rise"},
    "oversold": {"label": "RSI超賣(跌勢一面倒)", "codes": ["rsi_oversold", "w_rsi_oversold"], "varBg": "--fall-soft", "varText": "--fall"},
    "volume": {"label": "成交量異常", "codes": ["volume_spike", "w_volume_spike"], "varBg": "--vol-soft", "varText": "--vol"},
    "bias": {"label": "月線負乖離≥15%", "codes": BIAS_NEG, "varBg": "--warn-soft", "varText": "--warn"},
    "biaspos": {"label": "月線正乖離(參考)", "codes": BIAS_POS, "varBg": "--bg", "varText": "--ink-soft"},
    "wprov": {"label": "週線暫定(參考)", "codes": WP_CODES, "varBg": "--bg", "varText": "--ink-soft"},
    "cross": {"label": "交叉(參考)", "codes": CROSS, "varBg": "--bg", "varText": "--ink-soft"},
    "ma20": {"label": "月線(參考)", "codes": MA20_POS, "varBg": "--bg", "varText": "--ink-soft"},
    "ma5": {"label": "5日線(參考)", "codes": MA5_POS, "varBg": "--bg", "varText": "--ink-soft"},
}


TREND_METRICS = [
    {"key": "all", "label": "觸發檔數", "series": [{"name": "觸發", "codes": [c for c in SIGNAL_ORDER if c not in MA_POS_CODES and c not in WP_CODES], "color": "--accent"}]},
    {"key": "bs", "label": "強勢 vs 弱勢", "series": [
        {"name": "強勢趨勢", "codes": STRONG, "color": "--rise"},
        {"name": "弱勢趨勢", "codes": WEAK, "color": "--fall", "dash": "6 4"}]},
    {"key": "rsi", "label": "RSI 超買 vs 超賣", "note": "超買=近14日漲勢一面倒,超賣=跌勢一面倒。全市場超賣檔數暴增通常出現在急跌時。", "series": [
        {"name": "超買(漲勢一面倒)", "codes": ["rsi_overbought", "w_rsi_overbought"], "color": "--rise"},
        {"name": "超賣(跌勢一面倒)", "codes": ["rsi_oversold", "w_rsi_oversold"], "color": "--fall", "dash": "6 4"}]},
    {"key": "wk", "label": "週線強勢 vs 弱勢", "weekly": True,
     "note": "週線訊號只在週收盤判斷(遇週五休市則在下週第一個交易日),所以這張圖以週為單位。強勢=60週新高/週RSI超買/週線突破上軌,弱勢反之。",
     "series": [
        {"name": "週強勢", "codes": [c for c in STRONG if c.startswith("w_")], "color": "--rise"},
        {"name": "週弱勢", "codes": [c for c in WEAK if c.startswith("w_")], "color": "--fall", "dash": "6 4"}]},
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
    counter = Counter(industry_map.get(sid, "其他") for sid in sorted(stock_ids))
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))  # ties by name, so reruns agree
    return [f"{name}({cnt}檔)" for name, cnt in ranked[:top_n]]


def build_summary_rows(alerts: list[dict], universe: list[dict], total_universe: int) -> dict:
    """The day at a glance: a headline, an overall tone, and one short row per topic.
    Shared by Telegram (plain lines) and the board (a small labelled grid)."""
    industry_map = {s["stock_id"]: s.get("industry", "其他") for s in universe}
    by_stock = _group_by_stock([a for a in alerts if a["signal"] not in NOISY_CODES])
    if not by_stock:
        return {"headline": f"{total_universe}檔中沒有個股觸發訊號", "tone": "", "rows": []}

    ids = lambda codes: {a["stock_id"] for a in alerts if a["signal"] in codes}  # noqa: E731
    strong, weak = ids(STRONG_SET), ids(WEAK_SET)

    def top_ind(group: set) -> str:
        top = _top_industries(group, industry_map)
        return f"({top[0].split('(')[0]}居多)" if top else ""

    def names(group: set, n: int = 3) -> str:
        order = []
        for a in alerts:  # alerts follow the universe order (largest first)
            if a["stock_id"] in group and a["stock_name"] not in order:
                order.append(a["stock_name"])
        return "、".join(order[:n]) + ("等" if len(order) > n else "")

    if max(len(strong), len(weak)) < 0.05 * total_universe:
        tone = "盤勢平靜"  # a handful either way is not a direction
    elif len(strong) > len(weak) * 1.2:
        tone = "整體偏強"
    elif len(weak) > len(strong) * 1.2:
        tone = "整體偏弱"
    else:
        tone = "強弱互見"
    rows = [("強弱", f"強勢趨勢 {len(strong)} 檔{top_ind(strong) if strong else ''}・弱勢趨勢 {len(weak)} 檔{top_ind(weak) if weak else ''}")]

    ob, os_ = ids({"rsi_overbought"}), ids({"rsi_oversold"})
    share = len(os_) / total_universe if total_universe else 0
    level = "極端" if share >= 0.3 else "偏高" if share >= 0.1 else "正常"
    rows.append(("超買超賣", f"超賣 {len(os_)} 檔(全市場 {share:.0%},{level})・超買 {len(ob)} 檔"))

    bp, bn = ids(set(BIAS_POS)), ids(set(BIAS_NEG))
    if bp or bn:
        far_n = ids({"bias_neg_25", "bias_neg_35"})
        far_p = ids({"bias_pos_25", "bias_pos_35"})
        rows.append(("月線乖離", f"負乖離≥15% {len(bn)} 檔" + (f"(≥25% {len(far_n)} 檔)" if far_n else "")
                     + f"・正乖離≥15% {len(bp)} 檔" + (f"(≥25% {len(far_p)} 檔)" if far_p else "")))

    w_strong = ids({c for c in STRONG if c.startswith("w_")})
    w_weak = ids({c for c in WEAK if c.startswith("w_")})
    w_cross = ids({"wma_golden_cross", "wma_death_cross"})
    wp_up = ids({"wp_bb_breakout_upper", "wp_new_high", "wp_wma_golden_cross"})
    wp_dn = ids({"wp_bb_breakout_lower", "wp_new_low", "wp_wma_death_cross"})
    if w_strong or w_weak or w_cross:
        txt = (f"週收盤:強勢 {len(w_strong)} 檔" + (f"({names(w_strong)})" if w_strong else "")
               + f"・弱勢 {len(w_weak)} 檔" + (f"({names(w_weak)})" if w_weak else ""))
        rows.append(("週線", txt + ("・交叉見週線區塊" if w_cross else "")))
    elif wp_up or wp_dn:
        rows.append(("週線", f"本週暫定:突破/新高/金叉 {len(wp_up)} 檔・跌破/新低/死叉 {len(wp_dn)} 檔(週五收盤才確定)"))

    vol, above, below = ids({"volume_spike"}), ids({"close_above_ma20"}), ids({"close_below_ma20"})
    rows.append(("其他", f"量增 {len(vol)} 檔・站上月線 {len(above)} 檔・跌破月線 {len(below)} 檔"))
    return {"headline": f"{total_universe}檔中{len(by_stock)}檔觸發訊號", "tone": tone, "rows": rows}


def build_market_narrative(alerts: list[dict], universe: list[dict], total_universe: int) -> str:
    """Plain-text version (Telegram, local report): headline line, then one line per topic."""
    sm = build_summary_rows(alerts, universe, total_universe)
    head = sm["headline"] + (f" · {sm['tone']}" if sm["tone"] else "")
    return "\n".join([head] + [f"{label}:{text}" for label, text in sm["rows"]])


SUMMARY_CSS = """
.summary { display: flex; flex-direction: column; gap: 10px; }
.sum-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.tone { font-size: 14px; font-weight: 600; padding: 3px 12px; border-radius: 999px; background: var(--bg); color: var(--ink-soft); }
.tone.weak { background: var(--fall-soft); color: var(--fall); }
.tone.strong { background: var(--rise-soft); color: var(--rise); }
.sum-sub { font-size: 13px; color: var(--ink-soft); }
.sum-rows { display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; margin: 0; font-size: 14px; line-height: 1.55; }
.sum-rows dt { color: var(--ink-faint); font-size: 12.5px; padding-top: 2px; }
.sum-rows dd { margin: 0; min-width: 0; }
.sum-rows b { font-family: "IBM Plex Mono", monospace; font-weight: 600; font-size: 15px; }
.sum-rows .lvl-極端 { color: var(--paper); background: var(--fall); border-radius: 4px; padding: 0 5px; }
.sum-rows .lvl-偏高 { color: var(--fall); }
"""


def _summary_html(alerts: list[dict], universe: list[dict], total_universe: int) -> str:
    sm = build_summary_rows(alerts, universe, total_universe)
    cls = {"整體偏弱": "weak", "整體偏強": "strong"}.get(sm["tone"], "")
    rows = []
    for label, text in sm["rows"]:
        t = re.sub(r"(\d+%?)(?= 檔|,|\))", r"<b>\1</b>", text)
        t = re.sub(r",(極端|偏高)\)", r',<span class="lvl-\1">\1</span>)', t)
        rows.append(f"<dt>{label}</dt><dd>{t}</dd>")
    tone = f'<span class="tone {cls}">{sm["tone"]}</span>' if sm["tone"] else ""
    return (f'<div class="narrative summary"><div class="sum-head">{tone}<span class="sum-sub">{sm["headline"]}</span></div>'
            f'<dl class="sum-rows">{"".join(rows)}</dl></div>')

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
    '<td class="name">${stock.name}${mineTags(stock.stock_id)}</td>'
    '<td class="industry">${stock.industry}</td>'
    '<td>${badges}${newsHtml}</td>'
)

_CARD_HTML_FN_ARTIFACT = f"""
function cardHtml(stock) {{
  const badges = stock.signals.map(sigBadge).join('');
  const badgesHtml = badges ? `<div class="stock-card-badges">${{badges}}</div>` : '';
  const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join('');
  const newsHtml = news ? `<div class="news">${{news}}</div>` : '';
  const grid = {_CARD_STATS_JS}.map(([label, key, suffix]) =>
    `<div class="mini-stat"><p class="label">${{label}}</p><p class="value">${{fmt(stock[key], suffix)}}</p></div>`
  ).join('');
  return `<div class="stock-card">
    <div class="stock-card-head"><span class="code">${{stock.stock_id}}</span><span class="name">${{stock.name}}</span><span class="industry">${{stock.industry}}</span>${{listToggles(stock.stock_id)}}</div>
    ${{badgesHtml}}
    ${{stockChartHtml(stock)}}
    <details class="more-stats"><summary>全部指標數值<span class="ms-peek">RSI ${{fmt(stock.rsi)}} · 量比 ${{fmt(stock.vol_ratio, 'x')}} · 週RSI ${{fmt(stock.wrsi)}}</span></summary><div class="mini-grid">${{grid}}</div></details>
    ${{newsHtml}}
    ${{stockHistoryHtml(stock)}}
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
.wx-col.gold .wx-chip { background: var(--paper); color: var(--rise); box-shadow: inset 0 0 0 1px var(--rise); }
.wx-col.death .wx-chip { background: var(--paper); color: var(--fall); box-shadow: inset 0 0 0 1px var(--fall); }
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
.wx-prov { margin-top: 10px; padding: 10px 12px; border: 1px dashed var(--line-strong); border-radius: 8px; font-size: 12.5px; color: var(--ink-soft); line-height: 1.7; }
.wx-prov[hidden] { display: none; }
.wx-prov b { color: var(--ink); font-weight: 600; }
.wx-prov .g { color: var(--rise); margin-right: 4px; }
.wx-prov .x { color: var(--fall); margin-right: 4px; }
@media (max-width: 560px) { .wx-cols { grid-template-columns: 1fr; } }
"""

WEEKLY_CROSS_HTML = """
  <section id="wx" class="wx" aria-label="週線交叉">
    <div class="wx-head"><h2>週線交叉</h2><span id="wx-when" class="wx-when"></span></div>
    <div class="wx-cols">
      <div class="wx-col gold"><h3>黃金交叉 <b id="wx-g-n">0</b></h3><div id="wx-g" class="wx-chips"></div></div>
      <div class="wx-col death"><h3>死亡交叉 <b id="wx-d-n">0</b></h3><div id="wx-d" class="wx-chips"></div></div>
    </div>
    <div id="wx-prov" class="wx-prov" hidden></div>
    <details class="wx-prev"><summary>前幾週的週線交叉</summary><div id="wx-prev"></div></details>
    <p class="wx-note">5週線與20週線交叉,只在週收盤判斷。下一次週收盤之前,這裡都保留最近一週的結果;點股票可查看指標與走勢。<br>回測(2016–2026):週線死叉之後60個交易日平均只輸同期平均0.9%、且只在2021年後成立,金叉約0%。當作中期趨勢的參考,不是買賣訊號。</p>
  </section>
"""

WEEKLY_CROSS_JS = """
// Badge look follows the backtest: strong/weak continuation in red/green, crossovers as neutral outlines.
const WP_BULL_SET = new Set(["wp_wma_golden_cross", "wp_macd_golden_cross", "wp_bb_breakout_upper", "wp_new_high", "wp_rsi_overbought"]);
function sigStyle(code) {
  if (code.startsWith("wp_")) {
    const tone = WP_BULL_SET.has(code) ? "rise" : "fall";
    return `background:transparent;color:var(--${tone});border:1px dashed var(--${tone});padding:2px 8px`;
  }
  if (code.startsWith("bias_")) {
    const tone = code.startsWith("bias_pos") ? "rise" : "fall";
    return code.endsWith("_35") ? `background:var(--${tone});color:var(--paper);font-weight:600`
         : code.endsWith("_25") ? `background:var(--${tone}-soft);color:var(--${tone});font-weight:600;box-shadow:inset 0 0 0 1px var(--${tone})`
         : `background:var(--${tone}-soft);color:var(--${tone})`;
  }
  const cat = codeCategory(code);
  if (cat === "cross" || cat === "ma20" || cat === "ma5")
    return "background:transparent;color:var(--ink-soft);box-shadow:inset 0 0 0 1px var(--line-strong)";
  return badgeStyle(cat);
}
function sigBadge(sig) {
  const note = RSI_NOTE[sig.code];
  if (!note) return `<span class="badge" style="${sigStyle(sig.code)}">${sig.detail}</span>`;
  return `<span class="badge rsi" style="${sigStyle(sig.code)}" title="${note}">${sig.detail}<span class="bnote">${note}</span></span>`;
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
        openStock(sid);
      });
      el.appendChild(b);
    });
  };
  fill("wx-g", pick(last, gi));
  fill("wx-d", pick(last, di));
  const prov = document.getElementById("wx-prov");
  const pg = STOCKS.filter(s => s.signals.some(g => g.code === "wp_wma_golden_cross"));
  const pd = STOCKS.filter(s => s.signals.some(g => g.code === "wp_wma_death_cross"));
  if (!today && (pg.length || pd.length)) {
    const chip = s => `<button type="button" class="wx-link" data-sid="${s.stock_id}">${s.name}</button>`;
    prov.innerHTML = `<b>本週到目前為止(暫定,週五收盤才確定)</b>`
      + `<div><span class="g">金叉 ${pg.length}:</span>${pg.map(chip).join("、") || "—"}</div>`
      + `<div><span class="x">死叉 ${pd.length}:</span>${pd.map(chip).join("、") || "—"}</div>`;
    prov.hidden = false;
    prov.onclick = (e) => { const b = e.target.closest(".wx-link"); if (b) openStock(b.dataset.sid); };
  } else { prov.hidden = true; }
  const nm = list => list.length ? list.map(id => `<button type="button" class="wx-link" data-sid="${id}">${names[id] || id}</button>`).join("、") : "—";
  const prev = weekDays.slice(0, -1).slice(-6).reverse();
  document.getElementById("wx-prev").innerHTML = prev.length ? prev.map(d =>
    `<div class="wx-prev-row"><span class="d">${md(d.d)}</span><div><span class="g">金叉 ${pick(d, gi).length}:</span>${nm(pick(d, gi))}<br><span class="x">死叉 ${pick(d, di).length}:</span>${nm(pick(d, di))}</div></div>`
  ).join("") : '<p class="wx-none">還沒有更早的紀錄</p>';
  document.getElementById("wx-prev").onclick = (e) => {
    const b = e.target.closest(".wx-link"); if (b) openStock(b.dataset.sid);
  };
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
.row-link { cursor: pointer; }
.row-link:hover td.name, .row-link:focus-visible td.name { color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }
.row-link:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.th-hint { font-weight: 400; color: var(--ink-faint); margin-left: 8px; letter-spacing: 0; }
.wx-link { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; text-decoration: underline; text-decoration-color: var(--line-strong); text-underline-offset: 3px; }
.wx-link:hover { color: var(--accent); }
.wx-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
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
// Searching hides the trend chart and weekly panel above the search box and shows the navbar, so
// the page would jump. keepSearch() re-renders while holding the search box at the same spot on screen
// (and keeps the page tall enough that the browser doesn't clamp the scroll position).
function keepSearch(fn) {
  const box = document.querySelector(".search");
  if (!box) { fn(); return; }
  const before = box.getBoundingClientRect().top;
  document.body.style.minHeight = (document.documentElement.scrollHeight) + "px";
  fn();
  const shift = box.getBoundingClientRect().top - before;
  if (Math.abs(shift) > 1) window.scrollBy(0, shift);
  requestAnimationFrame(() => { document.body.style.minHeight = (window.scrollY + window.innerHeight) + "px"; });
}
function searchToView() {
  const box = document.querySelector(".search"), bar = document.getElementById("navbar");
  if (!box) { window.scrollTo(0, 0); return; }
  const offset = bar && !bar.hidden ? bar.getBoundingClientRect().height + 8 : 8;
  window.scrollTo(0, Math.max(0, box.getBoundingClientRect().top + window.scrollY - offset));
}
function navApply(st, scroll) {
  searchQuery = st.q; activeFilter = st.f;
  document.getElementById("search-input").value = st.q;
  if (scroll === "search") { render(); searchToView(); return; }
  if (typeof scroll === "number" || scroll === "top") document.body.style.minHeight = "";
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
function openStock(sid) {
  // land on the search box with the stock's card right below it, not the top of the page
  const cur = navState();
  if (cur.q === sid) { searchToView(); return; }
  NAV_STACK.push(cur);
  navApply({ q: sid, f: activeFilter }, "search");
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


GUIDE_CSS = """
.badge.rsi { white-space: normal; }
.badge .bnote { font-family: "IBM Plex Sans", "PingFang TC", sans-serif; font-size: 11px; opacity: .8; margin-left: 6px; }
.thermo { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; background: var(--paper); border: 1px solid var(--line);
  border-radius: 10px; padding: 12px 16px; margin-bottom: 18px; font-size: 13px; color: var(--ink-soft); line-height: 1.6; }
.thermo b { font-family: "IBM Plex Mono", monospace; font-size: 20px; font-weight: 500; color: var(--ink); }
.thermo .lvl { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--bg); color: var(--ink-soft); }
.thermo .lvl.hot { background: var(--fall-soft); color: var(--fall); }
.thermo .lvl.extreme { background: var(--fall); color: var(--paper); }
.thermo .t-note { flex-basis: 100%; font-size: 12px; color: var(--ink-faint); }
.guide { margin: -4px 0 16px; font-size: 13px; color: var(--ink-soft); }
.guide summary { cursor: pointer; width: fit-content; font-weight: 500; color: var(--accent); }
.guide summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.guide-body { background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; margin-top: 8px; line-height: 1.7; }
.guide-body dl { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; }
.guide-body dt { font-weight: 600; color: var(--ink); }
.guide-body dd { margin: 0; min-width: 0; }
.guide-body p { margin: 10px 0 0; font-size: 12px; color: var(--ink-faint); }
.guide-body p.tier-note { margin: 0 0 10px; font-size: 13px; color: var(--ink-soft); line-height: 1.7; }
@media (max-width: 560px) { .guide-body dl { grid-template-columns: 1fr; } .guide-body dd { margin-bottom: 6px; } }
"""

GUIDE_HTML = f"""
  <details class="guide">
    <summary>訊號怎麼看(回測 {BACKTEST['period']})</summary>
    <div class="guide-body">
      <p class="tier-note">訊號依回測證據分兩層。<b>核心</b>:強勢/弱勢趨勢、RSI超買/超賣、月線負乖離、成交量異常,十年回測有可測的差異。<b>參考</b>(篩選鈕上標「參考」):月線正乖離、各種交叉、週線暫定、5日線/月線,回測沒有優勢或樣本不可靠,只用來掌握盤面。訊號名稱只描述<em>現在</em>的狀態,不是預測;它之後怎麼走,看下面的回測和「實戰追蹤」。</p>
      <dl>
        <dt style="color:var(--rise)">強勢趨勢</dt><dd>{BACKTEST['strong']}。十年回測裡,強的股票傾向繼續強;但近半年實戰追蹤的結果相反,見「實戰追蹤」。</dd>
        <dt style="color:var(--fall)">弱勢趨勢</dt><dd>{BACKTEST['weak']}。弱的股票傾向繼續弱;跟著大盤一起跌時創新低的訊號較弱,大盤在漲卻創新低的才是真警訊。</dd>
        <dt>RSI超買</dt><dd>近14日的漲跌幅裡,上漲占了七成以上,也就是漲勢一面倒。名稱聽起來像「漲過頭該賣」,但回測顯示之後多半續強,不是賣訊。</dd>
        <dt>RSI超賣</dt><dd>近14日的漲跌幅裡,下跌占了七成以上,也就是跌勢一面倒。名稱聽起來像「跌過頭該買」,但回測顯示之後多半續弱,不是買訊;同時創新低的更弱。</dd>
        <dt style="color:var(--warn)">月線乖離</dt><dd>收盤價離20日均線(月線)多遠:(收盤÷月線−1)。分≥15%、≥25%、≥35%三級,正值代表漲離月線、負值代表跌離月線;每天只要還在範圍內就會列出,不是只在穿越那天。回測:正乖離之後平均報酬很高,但中位數接近0、勝率約五成,是少數大漲股拉高平均,一般情況沒有優勢;負乖離≥25%之後60個交易日中位數贏同期平均約8~12%、勝率67~80%,但只來自約120個交易日(集中在幾次大跌),而且股票池是事後的成分股,跌了沒回來的股票已被剔除,反彈幅度一定被高估。</dd>
        <dt>週線(本週暫定)</dt><dd>週一到週四,用當天收盤價當作本週收盤,先算一次週線訊號(虛線標籤)。週五收盤才是正式結果,中間可能出現又消失;週成交量因為一週還沒結束不列入。暫定訊號沒有回測,也不計入觸發檔數。</dd>
        <dt style="color:var(--vol)">成交量異常</dt><dd>{BACKTEST['volume']}。</dd>
        <dt>參考類</dt><dd>{BACKTEST['cross']}。保留給你掌握盤面,不建議當買賣依據。</dd>
      </dl>
      <p>回測方法:每個訊號觸發後的報酬,減掉同一天170檔的平均報酬,所以大盤漲跌不算訊號的功勞。限制:股票池是現在的成分股(挑了事後贏家,強勢訊號可能被高估)、用未還原股價。完整數字在 GitHub 的 backtest/results。</p>
    </div>
  </details>
"""


BREADTH_CSS = """
.breadth { background: var(--paper); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin: 0 0 16px; box-shadow: var(--shadow); }
.br-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.br-title { font-weight: 600; font-size: 14px; color: var(--ink); }
.br-read { font-size: 13px; color: var(--ink-soft); }
.br-read b { color: var(--ink); }
.br-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
.br-tile { background: var(--bg); border-radius: 8px; padding: 8px 10px; min-width: 0; }
.br-tile .l { font-size: 12px; color: var(--ink-soft); }
.br-tile .v { font-family: "IBM Plex Mono", monospace; font-size: 18px; white-space: nowrap; font-weight: 500; color: var(--ink); line-height: 1.3; }
.br-tile .v small { font-size: 12px; color: var(--ink-faint); font-weight: 400; margin-left: 4px; }
.br-tile .d { font-size: 11.5px; color: var(--ink-faint); }
.br-tile .up { color: var(--rise); } .br-tile .dn { color: var(--fall); }
.br-chart { margin-top: 10px; }
.br-chart svg { display: block; width: 100%; height: 70px; }
.br-legend { display: flex; gap: 12px; font-size: 11.5px; color: var(--ink-faint); margin-top: 2px; flex-wrap: wrap; }
.br-legend i { display: inline-block; width: 14px; height: 2px; vertical-align: 3px; margin-right: 4px; }
.br-note { font-size: 11.5px; color: var(--ink-faint); margin: 8px 0 0; line-height: 1.6; }
"""


def _breadth_html(b: dict | None, alerts: list[dict], m: dict) -> str:
    """市場廣度: read this before individual signals. Thresholds are descriptive, not backtested yet."""
    if not b or b.get("above60") is None:
        return ""
    n = b["n"] or 1
    hi = len({a["stock_id"] for a in alerts if a["signal"] == "new_high"}) / n
    lo = len({a["stock_id"] for a in alerts if a["signal"] == "new_low"}) / n
    a20, a60 = b["above20"], b["above60"]

    def chg(cur, prev):
        if prev is None:
            return ""
        d = (cur - prev) * 100
        cls = "up" if d > 0 else "dn" if d < 0 else ""
        return f'<div class="d">20天前 {prev:.0%},<span class="{cls}">{d:+.0f} 個百分點</span></div>'

    if a60 >= 0.6:
        struct = "<b>多數股票在季線之上</b>(多頭結構)"
    elif a60 <= 0.4:
        struct = "<b>多數股票跌破季線</b>(空頭結構)"
    else:
        struct = "<b>站上與跌破季線的股票各半</b>(結構分歧)"
    prev60 = b.get("above60_prev")
    trend = ""
    if prev60 is not None:
        d = a60 - prev60
        trend = ",比20天前明顯改善" if d >= 0.15 else ",比20天前明顯轉弱" if d <= -0.15 else ""
    lead = ""
    tiles = [
        f'<div class="br-tile"><div class="l">站上月線(20日)</div><div class="v">{a20:.0%}</div>{chg(a20, b.get("above20_prev"))}</div>',
        f'<div class="br-tile"><div class="l">站上季線(60日)</div><div class="v">{a60:.0%}</div>{chg(a60, prev60)}</div>',
        f'<div class="br-tile"><div class="l">創60日新高 / 新低</div><div class="v"><span class="up">{hi:.0%}</span>'
        f'<small>/</small> <span class="dn">{lo:.0%}</span></div><div class="d">占全部{n}檔</div></div>',
    ]
    if b.get("bench20") is not None:
        bn, md = b["bench20"], b["med20"]
        gap = bn - md
        if gap >= 0.03:
            lead = (f";近一個月<b>權值股比一般股票強</b>({b['bench_name']} {bn:+.1%} vs 一般股票 {md:+.1%}"
                    + (",漲勢集中在少數大型股)" if bn > 0 and md <= 0.01 else ")"))
        elif gap <= -0.03:
            lead = f";近一個月<b>一般股票比權值股強</b>(一般股票 {md:+.1%} vs {b['bench_name']} {bn:+.1%})"
        tiles.append(f'<div class="br-tile"><div class="l">近20日:{b["bench_name"]} vs 一般股票</div>'
                     f'<div class="v"><span class="{"up" if bn >= 0 else "dn"}">{bn:+.1%}</span><small>vs</small> '
                     f'<span class="{"up" if md >= 0 else "dn"}">{md:+.1%}</span></div>'
                     f'<div class="d">一般股票={n}檔報酬的中位數</div></div>')

    ser = b.get("series") or {}
    chart = ""
    if len(ser.get("dates", [])) > 5:
        w, h, k = 600, 70, len(ser["dates"]) - 1

        def path(vals):
            return " ".join(f"{'M' if i == 0 else 'L'}{i / k * w:.1f},{h - v * h:.1f}" for i, v in enumerate(vals))
        chart = (f'<div class="br-chart"><svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" '
                 f'aria-label="站上月線與季線比例,近{k + 1}個交易日">'
                 f'<line x1="0" x2="{w}" y1="{h / 2}" y2="{h / 2}" stroke="var(--line-strong)" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/>'
                 f'<path d="{path(ser["above20"])}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/>'
                 f'<path d="{path(ser["above60"])}" fill="none" stroke="var(--warn)" stroke-width="2" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>'
                 f'</svg><div class="br-legend"><span><i style="background:var(--accent)"></i>站上月線</span>'
                 f'<span><i style="background:var(--warn)"></i>站上季線</span><span>虛線=50%</span>'
                 f'<span>{ser["dates"][0]} ~ {ser["dates"][-1]}</span></div></div>')
    return (f'  <section class="breadth"><div class="br-head"><span class="br-title">市場廣度 · 先看大環境</span>'
            f'<span class="br-read">{struct}{trend}{lead}。</span></div>'
            f'<div class="br-grid">{"".join(tiles)}</div>{chart}'
            f'<p class="br-note">同一個訊號在不同環境下意義不同,所以先看這裡再看個股。「多頭/空頭結構」只是描述目前狀態'
            f'(站上季線比例≥60%/≤40%),這些門檻還沒用回測驗證過,下一階段會用十年資料檢驗。</p></section>')


def _thermo_html(alerts: list[dict], total: int, note: str | None = None) -> str:
    """Market-wide share of stocks on a daily RSI-oversold reading: a temperature gauge, not a signal."""
    n = len({a["stock_id"] for a in alerts if a["signal"] == "rsi_oversold"})
    share = n / total if total else 0
    if share >= 0.3:
        lvl, cls = "極端超賣", "extreme"
    elif share >= 0.1:
        lvl, cls = "偏高", "hot"
    else:
        lvl, cls = "正常", ""
    return (f'  <div class="thermo"><span>市場溫度計 · 全市場RSI超賣比例</span><b>{share:.0%}</b>'
            f'<span>({n}/{total}檔)</span><span class="lvl {cls}">{lvl}</span>'
            f'<span class="t-note">{BACKTEST["thermo"] if note is None else note}。</span></div>')


# ---- 我的持股 / 我的關注 (artifact / Pages only) ----
# Kept in the artifact's db (doc lists/main, owner-only) so it follows the owner across devices and
# never lands in this public repo. Where db is unavailable (GitHub Pages, signed out) it falls back
# to this browser's localStorage.
LISTS_CSS = """
.list-btns { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
.list-btn { font-family: inherit; font-size: 12.5px; padding: 5px 10px; border-radius: 999px; border: 1px solid var(--line-strong);
  background: var(--paper); color: var(--ink-soft); cursor: pointer; }
.list-btn:hover { border-color: var(--accent); }
.list-btn.on { background: var(--accent); border-color: var(--accent); color: var(--paper); }
.list-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.filters button.mine { border-style: dashed; }
.filters button.mine.active { border-style: solid; }
.tag-mine { display: inline-block; font-size: 10.5px; padding: 1px 6px; border-radius: 4px; margin-left: 6px; vertical-align: 1px;
  background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.no-sig { color: var(--ink-faint); font-size: 12.5px; }
.list-note { font-size: 12.5px; color: var(--ink-faint); margin: -6px 0 14px; }
.list-note[hidden] { display: none; }
"""

LISTS_JS = """
const LISTS = { hold: [], watch: [] };
const LIST_LABEL = { hold: "我的持股", watch: "我的關注" };
let listRef = null, listMode = "local";
function listsFromLocal() {
  try { const v = JSON.parse(localStorage.getItem("tw-signal-lists") || "{}"); LISTS.hold = v.hold || []; LISTS.watch = v.watch || []; } catch (e) {}
}
function saveLists() {
  const body = { hold: LISTS.hold.slice(), watch: LISTS.watch.slice() };
  if (listRef) { listRef.set(body).catch(() => { listMode = "error"; render(); }); return; }
  try { localStorage.setItem("tw-signal-lists", JSON.stringify(body)); } catch (e) {}
}
function inList(key, sid) { return LISTS[key].includes(sid); }
function toggleList(key, sid) {
  LISTS[key] = inList(key, sid) ? LISTS[key].filter(x => x !== sid) : LISTS[key].concat([sid]);
  saveLists(); render();
}
function listToggles(sid) {
  return '<span class="list-btns">' + ["hold", "watch"].map(k =>
    `<button type="button" class="list-btn${inList(k, sid) ? " on" : ""}" data-list="${k}" data-sid="${sid}">${inList(k, sid) ? "✓ " : "+ "}${LIST_LABEL[k]}</button>`
  ).join("") + "</span>";
}
function mineTags(sid) {
  return (inList("hold", sid) ? '<span class="tag-mine">持股</span>' : "") + (inList("watch", sid) ? '<span class="tag-mine">關注</span>' : "");
}
function listNote() {
  const el = document.getElementById("list-note");
  const showing = !searchQuery.trim() && (activeFilter === "hold" || activeFilter === "watch");
  el.hidden = !showing;
  if (!showing) return;
  const where = listMode === "db" ? "清單存在你的帳號,換裝置也看得到。"
              : listMode === "error" ? "清單沒有存成功,請重新整理再試一次。"
              : "清單只存在這個瀏覽器。";
  el.textContent = `搜尋股票,在個股頁按「+ 我的持股」或「+ 我的關注」就能加入或移除。${where}`;
}
document.getElementById("cards").addEventListener("click", (e) => {
  const b = e.target.closest(".list-btn"); if (b) toggleList(b.dataset.list, b.dataset.sid);
});
listsFromLocal();
(async () => {
  const db = window.claude && window.claude.use ? await window.claude.use("db").catch(() => null) : null;
  if (!db) return;
  const ref = db.doc("lists/main");
  let first = true;
  const timer = setTimeout(() => { if (first) { listMode = "local"; render(); } }, 10000);
  ref.onSnapshot(snap => {
    clearTimeout(timer);
    const v = snap.exists ? (snap.data() || {}) : {};
    if (first && !snap.exists && (LISTS.hold.length || LISTS.watch.length)) {
      listRef = ref; listMode = "db"; first = false; saveLists(); render(); return;  // carry this browser's list over once
    }
    first = false; listRef = ref; listMode = "db";
    LISTS.hold = Array.isArray(v.hold) ? v.hold : []; LISTS.watch = Array.isArray(v.watch) ? v.watch : [];
    render();
  }, () => { clearTimeout(timer); listRef = null; listMode = "local"; render(); });
})();
"""


TRACK_CSS = """
.tk-intro { margin: 0 0 12px; font-size: 13px; color: var(--ink-soft); line-height: 1.7; }
.tk-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.tk-card { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; background: var(--paper); min-width: 0; }
.tk-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.tk-name { font-weight: 600; font-size: 14px; color: var(--ink); }
.tk-pill { font-size: 12px; padding: 2px 9px; border-radius: 999px; background: var(--bg); color: var(--ink-soft); white-space: nowrap; }
.tk-pill.up { background: var(--rise-soft); color: var(--rise); }
.tk-pill.down { background: var(--fall-soft); color: var(--fall); }
.tk-pill.mixed { background: var(--warn-soft); color: var(--warn); }
.tk-say { font-size: 13px; color: var(--ink); line-height: 1.6; margin: 0 0 8px; }
.tk-say b { font-family: "IBM Plex Mono", monospace; }
.tk-bar { position: relative; height: 10px; background: var(--bg); border-radius: 5px; margin: 4px 0 8px; }
.tk-bar::after { content: ""; position: absolute; left: 50%; top: -3px; bottom: -3px; width: 1px; background: var(--line-strong); }
.tk-bar i { position: absolute; top: 0; bottom: 0; border-radius: 5px; }
.tk-meta { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 11.5px; color: var(--ink-faint); }
.tk-meta .ok { color: var(--ink-soft); }
.tk-meta .warn { color: var(--warn); }
.tk-split { margin: 0 0 8px; padding: 6px 8px; background: var(--bg); border-radius: 6px; font-size: 12px; }
.tk-rg { display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; line-height: 1.7; }
.tk-rg .k { color: var(--ink-soft); min-width: 5.5em; }
.tk-rg .v { color: var(--ink); }
.tk-rg .pos { color: var(--rise); font-weight: 600; }
.tk-rg .neg { color: var(--fall); font-weight: 600; }
.tk-rg .na, .tk-rg .n { color: var(--ink-faint); }
.tk-rg .n { margin-left: 2px; font-size: 11px; }
.tk-rg .ref { margin-left: auto; color: var(--ink-faint); font-size: 11.5px; }
.tk-raw { margin-top: 12px; }
.tk-raw .tbl { overflow-x: auto; }
.tk-raw table { min-width: 560px; font-size: 12.5px; }
.tk-raw th, .tk-raw td { padding: 6px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--line); }
.tk-raw th:first-child, .tk-raw td:first-child { text-align: left; }
.tk-raw td.v { font-family: "IBM Plex Mono", monospace; }
.tk-raw .n { color: var(--ink-faint); font-size: 11px; margin-left: 4px; }
.tk-raw .pos { color: var(--rise); }
.tk-raw .neg { color: var(--fall); }
.tk-raw .na { color: var(--ink-faint); }
"""


def _verdict(st: dict) -> tuple[str, str]:
    """Plain-language reading of one horizon's numbers: (text, css class)."""
    m, h = st["mean"], st["hit"]
    if m >= 0.005 and h >= 0.52:
        return "之後多半跑贏大盤", "up"
    if m <= -0.005 and h <= 0.48:
        return "之後多半跑輸大盤", "down"
    if m >= 0.005:
        return "多數小輸、少數大贏", "mixed"
    if m <= -0.005:
        return "多數小贏、少數大輸", "mixed"
    return "跟大盤差不多", ""


def _regime_split(g: dict, h: str) -> str:
    """Same signal split by market backdrop (universe down vs up over the past 60 trading days),
    each next to what ten years of backtest saw in the same backdrop."""
    rg, bt = g.get("regime") or {}, g.get("backtest_regime") or {}
    lines = []
    for key, name in (("down", "大盤弱時"), ("up", "大盤不弱時")):
        st = (rg.get(key) or {}).get(h) or {}
        b = (bt.get(key) or {}).get(h)
        if st.get("n", 0) >= 10:
            m = st["mean"] * 100
            live = (f'<span class="{"pos" if m >= 0 else "neg"}">{"強" if m >= 0 else "弱"}{abs(m):.1f}%</span>'
                    f',{st["hit"] * 100:.0f}%跑贏<span class="n">({st["n"]}次)</span>')
        else:
            live = f'<span class="na">樣本太少({st.get("n", 0)}次)</span>'
        ref = (f'<span class="ref">回測:{"強" if b >= 0 else "弱"}{abs(b) * 100:.1f}%</span>' if b is not None else "")
        lines.append(f'<div class="tk-rg"><span class="k">{name}</span><span class="v">{live}</span>{ref}</div>')
    return f'<div class="tk-split">{"".join(lines)}</div>'


def _track_html(tracking: dict | None, n_universe: int = 170) -> str:
    """實戰追蹤 as cards: a plain verdict, a bar for how far above/below the market, and how much to trust it."""
    if not tracking or not tracking.get("groups"):
        return ""
    cards = []
    for g in tracking["groups"]:
        h = "20" if (g.get("20") or {}).get("n", 0) >= 10 else "5"
        st = g.get(h) or {}
        if not st.get("n"):
            cards.append(f'<div class="tk-card"><div class="tk-head"><span class="tk-name">{g["label"]}</span>'
                         f'<span class="tk-pill">還沒有結果</span></div><p class="tk-say">'
                         + (f'出現過 {g["fired"]} 次,但都還沒滿 5 個交易日,過幾天才算得出來。' if g["fired"]
                            else '追蹤以來還沒出現過。') + '</p></div>')
            continue
        text, cls = _verdict(st)
        m, hit = st["mean"] * 100, st["hit"] * 100
        days = "20 個交易日(約一個月)" if h == "20" else "5 個交易日(約一週)"
        say = (f"出現後 {days},有 <b>{hit:.0f}%</b> 的次數跑贏大盤,"
               f"平均比大盤{'強' if m >= 0 else '弱'} <b>{abs(m):.1f}%</b>。")
        width = min(abs(m), 10) / 10 * 50
        color = "var(--rise)" if m >= 0 else "var(--fall)"
        pos = f"left:50%;width:{width:.1f}%" if m >= 0 else f"left:{50 - width:.1f}%;width:{width:.1f}%"
        meta = []
        s60 = g.get("60") or {}
        if s60.get("n", 0) >= 10 and h != "60":
            meta.append(f'<span>三個月後:比大盤{"強" if s60["mean"] >= 0 else "弱"}{abs(s60["mean"]) * 100:.1f}%,{s60["hit"] * 100:.0f}%跑贏</span>')
        bt = g.get("backtest60")
        if bt is not None:
            has60 = s60.get("n", 0) >= 10
            ref = s60["mean"] if has60 else st["mean"]
            span = "三個月後的方向" if has60 else "目前的方向"
            if abs(bt) < 0.005:
                meta.append('<span>10年回測:三個月後沒有方向</span>')
            elif (bt > 0) == (ref > 0):
                meta.append(f'<span class="ok">{span}跟10年回測一致</span>')
            else:
                meta.append(f'<span class="warn">{span}跟10年回測相反</span>')
        ep, nd = st.get("episodes"), st.get("dates")
        if ep is not None:
            # consecutive days of one sell-off are one event: trust follows the number of separate episodes
            level = "低" if ep < 6 or st["n"] < 30 else "中" if ep < 15 else "高"
            cls_r = "warn" if level == "低" else "ok" if level == "高" else ""
            meta.append(f'<span class="{cls_r}">可信度{level}(只算得上{ep}段互不重疊的行情;{st["n"]}次訊號)</span>')
        split = _regime_split(g, h)
        cards.append(f'<div class="tk-card"><div class="tk-head"><span class="tk-name">{g["label"]}</span>'
                     f'<span class="tk-pill {cls}">{text}</span></div><p class="tk-say">{say}</p>'
                     f'<div class="tk-bar" title="跟大盤比 {m:+.1f}%(長條滿格=±10%)"><i style="{pos};background:{color}"></i></div>'
                     f'{split}<div class="tk-meta">{"".join(meta)}</div></div>')

    def cell(st: dict | None) -> str:
        if not st or not st.get("n"):
            return '<td class="v na">—</td>'
        mm = st["mean"] * 100
        return (f'<td class="v"><span class="{"pos" if mm > 0 else "neg"}">{mm:+.1f}%</span> · {st["hit"] * 100:.0f}%'
                f'<span class="n">n={st["n"]}</span></td>')
    rows = []
    for g in tracking["groups"]:
        bt = g.get("backtest60")
        bt_cell = f'<td class="v"><span class="{"pos" if bt > 0 else "neg"}">{bt * 100:+.1f}%</span></td>' if bt is not None else '<td class="v na">—</td>'
        rows.append(f'<tr><td>{g["label"]}</td><td class="v">{g["fired"]}</td>{cell(g.get("5"))}{cell(g.get("20"))}{cell(g.get("60"))}{bt_cell}</tr>')
    seeded = "前段是用當時價格重算出來的訊號,之後才是每天實際顯示的訊號。" if tracking.get("seeded_from_history") else ""
    return f"""
  <details class="guide">
    <summary>實戰追蹤(自 {tracking['since']} 起的真實訊號)</summary>
    <div class="guide-body">
      <p class="tk-intro">每張卡片回答一個問題:這個訊號出現後,那檔股票有沒有比大盤({n_universe}檔平均)強?「跑贏」是指比大盤強,不一定是上漲:大盤跌10%、它只跌5%,也算跑贏。長條往右(紅)是平均跑贏、往左(綠)是跑輸,滿格代表10%。可信度看的不是訊號次數,而是有幾段互不重疊的行情:同一波大跌連續好幾天、幾十檔一起觸發,其實只算一件事。累積到15段以上才算「高」,目前追蹤才半年,大多還是「低」。灰色小框把同一個訊號拆成兩種盤勢:「大盤弱」是指{n_universe}檔平均過去三個月(60個交易日)下跌,右邊是10年回測在同樣盤勢下的平均,用來判斷結果是訊號本身的效果,還是只因為碰上大跌後的反彈。</p>
      <div class="tk-grid">{''.join(cards)}</div>
      <details class="tk-raw"><summary>看完整數字</summary><div class="tbl"><table>
        <thead><tr><th>訊號</th><th>出現次數</th><th>5日後</th><th>20日後</th><th>60日後</th><th>回測60日</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table></div>
        <p>格式:平均超額報酬 · 勝率(跑贏大盤的比例),n=已滿該天數的次數。{seeded}</p></details>
    </div>
  </details>
"""


WX_TW_NOTE = "<br>回測(2016–2026):週線死叉之後60個交易日平均只輸同期平均0.9%、且只在2021年後成立,金叉約0%。當作中期趨勢的參考,不是買賣訊號。"


def _us_guide(results_path: Path, n_universe: int) -> str:
    """US guide: plain definitions plus the US backtest's 60-day numbers when they exist."""
    bt = {}
    try:
        bt = json.loads(results_path.read_text(encoding="utf-8"))["signals"]
    except (OSError, ValueError, KeyError):
        pass

    def line(codes: list[str]) -> str:
        vals = [bt[c]["60"]["all"] for c in codes if c in bt and bt[c]["60"]["all"].get("n")]
        if not vals:
            return "美股回測還沒跑完。"
        n = sum(v["n"] for v in vals)
        mean = sum(v["excess_mean"] * v["n"] for v in vals) / n
        med = sum(v["excess_median"] * v["n"] for v in vals) / n
        hit = sum(v["hit"] * v["n"] for v in vals) / n
        return f"美股回測:之後60個交易日平均{mean * 100:+.1f}%、中位數{med * 100:+.1f}%、勝率{hit * 100:.0f}%(n={n})。"

    rows = [
        ("強勢趨勢", "var(--rise)", "創新高、RSI超買、突破布林上軌(日線與週線)。", STRONG),
        ("弱勢趨勢", "var(--fall)", "創新低、RSI超賣、跌破布林下軌(日線與週線)。", WEAK),
        ("RSI超買", "", "近14日的漲跌幅裡上漲占七成以上,漲勢一面倒。", ["rsi_overbought"]),
        ("RSI超賣", "", "近14日的漲跌幅裡下跌占七成以上,跌勢一面倒。", ["rsi_oversold"]),
        ("月線乖離", "var(--warn)", "收盤價離20日均線多遠,分≥15%、≥25%、≥35%三級;負乖離≥25%:", ["bias_neg_25", "bias_neg_35"]),
        ("成交量異常", "var(--vol)", "成交量是5日均量的2倍以上。", ["volume_spike"]),
        ("週線交叉", "", "5週線與20週線交叉,只在週收盤判斷;死叉:", ["wma_death_cross"]),
        ("參考類", "", "均線、MACD交叉與站上/跌破5日線、月線。", ["ma_golden_cross", "ma_death_cross", "macd_golden_cross", "macd_death_cross"]),
    ]
    body = "".join(
        (f'<dt style="color:{c}">' if c else "<dt>") + f"{t}</dt><dd>{d}{line(codes)}</dd>" for t, c, d, codes in rows)
    return f"""
  <details class="guide">
    <summary>訊號怎麼看(美股)</summary>
    <div class="guide-body">
      <dl>{body}</dl>
      <p>回測方法跟台股版相同:每個訊號之後的報酬減掉同一天{n_universe}檔的平均。美股用還原權息價格,但股票池仍是現在的成分股(事後贏家),強勢訊號可能被高估。台股回測的結論不能直接套用到美股。</p>
    </div>
  </details>
"""


MARKET_TW = {
    "key": "tw", "title": "台股訊號板", "desc": "台灣50與中型100成分股每日技術指標監測,收盤後自動更新",
    "subhead": "台灣50 + 中型100 成分股 · 每個交易日收盤後自動更新", "universe": "台灣50+中型100",
    "placeholder": "搜尋代號或名稱(例如 2330 或 台積電),查任一檔目前指標數值", "source": "FinMind",
}
MARKET_US = {
    "key": "us", "title": "美股訊號板", "desc": "Nasdaq-100與費城半導體成分股每日技術指標監測",
    "subhead": "Nasdaq-100 + 費城半導體成分股 · 美股每個交易日收盤後更新(台灣早上)", "universe": "Nasdaq-100+費半",
    "placeholder": "搜尋代號或名稱(例如 NVDA 或 Micron),查任一檔目前指標數值", "source": "Yahoo Finance(還原權息價格)",
}


def build_artifact_html(run_date: str, alerts: list[dict], universe: list[dict], news_map: dict | None = None,
                         snapshots: list[dict] | None = None, history: dict | None = None,
                         series: dict | None = None, tracking: dict | None = None, market: dict | None = None,
                         breadth: dict | None = None) -> str:
    """Standalone page matching the published Claude Artifact's design (red=偏多/rise, green=偏空/fall per TWSE convention). The scheduled task reads this file's content and republishes it to the same artifact URL each trading day."""
    m = market or MARKET_TW
    # Stocks with no price for the day (delisted, taken private, data gap) are not evaluated; count what was.
    n_eval = len(snapshots) if snapshots else len(universe)
    seen = {s["stock_id"] for s in snapshots or []}
    missing = [s for s in universe if s["stock_id"] not in seen] if snapshots else []
    missing_html = ('<p class="label" style="margin:6px 0 0" title="名單內但當天沒有報價,未納入計算">缺 '
                    + "、".join(html.escape(s["name"]) for s in missing[:4]) + ("…" if len(missing) > 4 else "") + "</p>"
                    ) if missing else ""
    us = m["key"] == "us"
    guide_html = _us_guide(Path(__file__).resolve().parent.parent / "backtest" / "results_us" / "results.json", n_eval) if us else GUIDE_HTML
    wx_html = WEEKLY_CROSS_HTML.replace(WX_TW_NOTE, "") if us else WEEKLY_CROSS_HTML
    lists_js = LISTS_JS.replace("tw-signal-lists", f"{m['key']}-signal-lists")
    rsi_note = {k: v.split(";")[0] for k, v in RSI_NOTE.items()} if us else RSI_NOTE
    thermo_note = "美股版的超賣比例門檻沿用台股的分級,尚未用美股資料驗證" if us else None
    narrative = build_market_narrative(alerts, universe, n_eval)
    payload = _build_unified_payload(alerts, universe, news_map, snapshots)
    triggered_count = len({a["stock_id"] for a in alerts if a["signal"] not in NOISY_CODES})
    hist_json = json.dumps(history or {"codes": [], "days": []}, ensure_ascii=False, separators=(",", ":"))
    series_json = json.dumps(series or {"dates": [], "v": {}}, ensure_ascii=False, separators=(",", ":"))
    siglabel_json = json.dumps(SIGNAL_SECTION_TITLE, ensure_ascii=False)
    weekday = "日一二三四五六"[__import__("datetime").date.fromisoformat(run_date).isoweekday() % 7]

    return f"""<title>{m["title"]}</title>
<meta name="description" content="{m["desc"]}">
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
.more-stats {{ margin: 0 0 4px; }}
.more-stats summary {{ cursor: pointer; font-size: 13px; font-weight: 500; color: var(--accent); padding: 6px 0; width: fit-content; }}
.more-stats summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.more-stats .ms-peek {{ font-family: "IBM Plex Mono", monospace; font-weight: 400; color: var(--ink-soft); margin-left: 10px; font-size: 12.5px; }}
.more-stats[open] .ms-peek {{ display: none; }}
.more-stats .mini-grid {{ margin-top: 6px; }}
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
{GUIDE_CSS}
{LISTS_CSS}
{TRACK_CSS}
{SUMMARY_CSS}
{BREADTH_CSS}
</style>

<div class="wrap">
{NAV_HTML}
  <div class="masthead">
    <h1>{m["title"]}</h1>
    <span class="date">{run_date}(週{weekday})</span>
  </div>
  <p class="subhead">{m["subhead"]}</p>
  {_summary_html(alerts, universe, n_eval)}
{_breadth_html(breadth, alerts, m)}
  <div class="stats">
    <div class="stat"><p class="label">監測檔數</p><p class="value">{n_eval}</p>{missing_html}</div>
    <div class="stat"><p class="label">觸發訊號</p><p class="value">{triggered_count}</p></div>
    <div class="stat"><p class="label">強勢趨勢</p><p class="value rise">{len({a["stock_id"] for a in alerts if a["signal"] in STRONG_SET})}</p></div>
    <div class="stat"><p class="label">弱勢趨勢</p><p class="value fall">{len({a["stock_id"] for a in alerts if a["signal"] in WEAK_SET})}</p></div>
  </div>
{_thermo_html(alerts, n_eval, thermo_note)}
{wx_html}
{trend_ui.TREND_HTML}
  <div class="search">
    <input type="text" id="search-input" placeholder="{m["placeholder"]}">
    <button type="button" id="search-clear">清除</button>
  </div>

  <div id="filters" class="filters"></div>
  <p id="list-note" class="list-note" hidden></p>
{guide_html}{_track_html(tracking, n_eval)}
  <div id="table-wrap" class="table-wrap">
    <table>
      <thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>觸發訊號 <span class="th-hint">點任一列看個股</span></th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div id="cards" class="cards" style="display:none"></div>
  <p id="empty-msg"></p>
  <div class="legend">
    <span><i class="dot" style="background:var(--rise)"></i>強勢趨勢:創新高/RSI超買/突破布林上軌(日線與週線)</span>
    <span><i class="dot" style="background:var(--fall)"></i>弱勢趨勢:創新低/RSI超賣/跌破布林下軌(日線與週線)</span>
    <span><i class="dot" style="background:var(--vol)"></i>成交量異常</span>
    <span><i class="dot" style="background:var(--warn)"></i>月線乖離≥15%/25%/35%(紅=漲離、綠=跌離;顏色越深級數越高)</span>
    <span><i class="dot" style="background:var(--line-strong)"></i>參考:均線/MACD/週線交叉、站上/跌破5日線與月線({"" if us else "回測預測力接近0;"}5日線不計入觸發檔數)</span>
  </div>
  <footer>資料來源:{m["source"]} · 指標:MA交叉/收盤穿越5日線與月線/RSI/MACD/布林通道/成交量/新高新低,日線與週線各算一套(週線用5週vs20週、60週新高低,只在週收盤判斷;卡片上週線數值為含本週的暫時值),任一觸發即列入 · 搜尋可查全部{n_eval}檔目前數值 · 僅供個人參考,非投資建議</footer>
</div>

<script>
const STOCKS = {json.dumps(payload, ensure_ascii=False)};
const CATS = {json.dumps(ARTIFACT_CATEGORIES, ensure_ascii=False)};
const HIST = {hist_json};
const SER = {series_json};
const VOL_UNIT = {json.dumps('' if us else ' 張')};
const SIGLABEL = {siglabel_json};
const TREND_METRICS = {json.dumps(TREND_METRICS, ensure_ascii=False)};
const BULL_CODES = {json.dumps(sorted(BULLISH_SIGNALS))};
const BEAR_CODES = {json.dumps(sorted(BEARISH_SIGNALS))};
const NOISY = new Set({json.dumps(sorted(NOISY_CODES))});
const RSI_NOTE = {json.dumps(rsi_note, ensure_ascii=False)};
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
  counts.hold = LISTS.hold.length; counts.watch = LISTS.watch.length;
  const items = [["all", "全部"], ["hold", "我的持股"], ["watch", "我的關注"]].concat(Object.keys(CATS).map(k => [k, CATS[k].label]));
  items.forEach(([key, label]) => {{
    const btn = document.createElement("button"); btn.type = "button";
    btn.textContent = `${{label}} (${{counts[key]}})`;
    btn.className = (key === activeFilter ? "active" : "") + (key === "hold" || key === "watch" ? " mine" : "");
    btn.addEventListener("click", () => {{ navTo({{ q: "", f: key }}); }});
    el.appendChild(btn);
  }});
}}

function getVisible() {{
  if (searchQuery.trim()) {{
    const exact = STOCKS.filter(s => s.stock_id === searchQuery.trim());
    return exact.length ? exact : STOCKS.filter(s => matchesSearch(s, searchQuery));
  }}
  if (activeFilter === "hold" || activeFilter === "watch") return STOCKS.filter(s => inList(activeFilter, s.stock_id));
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
  listNote();
  const emptyMsg = document.getElementById("empty-msg");
  const tableWrap = document.getElementById("table-wrap");
  const cardsWrap = document.getElementById("cards");

  if (!visible.length) {{
    emptyMsg.style.display = "block";
    emptyMsg.textContent = searching
      ? `查無「${{searchQuery}}」相關股票(僅收錄{m["universe"]}共{n_eval}檔)`
      : (activeFilter === "hold" || activeFilter === "watch") ? `${{LIST_LABEL[activeFilter]}}還是空的。`
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
    const badges = stock.signals.map(sigBadge).join("") || '<span class="no-sig">今日無訊號</span>';
    const news = (stock.news || []).map(n => `<a href="${{n.link}}" target="_blank" rel="noopener">↗ ${{n.title}}</a>`).join("");
    const newsHtml = news ? `<div class="news">${{news}}</div>` : "";
    tr.innerHTML = `{_ROW_HTML_ARTIFACT}`;
    tr.className = "row-link"; tr.tabIndex = 0;
    tr.title = `看 ${{stock.name}} 的指標與走勢`;
    tr.addEventListener("click", (e) => {{ if (!e.target.closest("a")) openStock(stock.stock_id); }});
    tr.addEventListener("keydown", (e) => {{ if (e.key === "Enter") openStock(stock.stock_id); }});
    rows.appendChild(tr);
  }});
}}

document.getElementById("search-input").addEventListener("input", (e) => {{
  if (!searchQuery.trim() && e.target.value.trim()) NAV_STACK.push(navState());
  searchQuery = e.target.value; keepSearch(render);
}});
document.getElementById("search-clear").addEventListener("click", () => {{
  if (!searchQuery) return;
  NAV_STACK.push(navState()); searchQuery = ""; document.getElementById("search-input").value = ""; keepSearch(render);
}});
{NAV_JS}
{lists_js}
renderTrend();
renderWeeklyCross();
render();
</script>
"""


def write_artifact_source(report_dir: str, run_date: str, alerts: list[dict], universe: list[dict],
                           news_map: dict | None = None, snapshots: list[dict] | None = None,
                           history: dict | None = None, series: dict | None = None, tracking: dict | None = None,
                           breadth: dict | None = None) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{run_date}_artifact.html"
    path.write_text(build_artifact_html(run_date, alerts, universe, news_map, snapshots, history, series, tracking,
                                        breadth=breadth), encoding="utf-8")
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
