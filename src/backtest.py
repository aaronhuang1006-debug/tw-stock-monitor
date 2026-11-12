"""Backtest of the board's signals: what happened to a stock after each signal fired.

Run in GitHub Actions (FinMind is reachable there):  python -m src.backtest
Writes backtest/results/results.json and backtest/results/summary.md.

Method
- Universe: the board's 170 stocks (config/universe.json), from --start (default 2016-01-01).
- Prices: FinMind TaiwanStockPriceAdj (dividend/split-adjusted) when the account can read it,
  otherwise raw TaiwanStockPrice. With raw prices, any event whose forward window contains a
  one-day move beyond ±11% (Taiwan's limit is ±10%, so that is a split or a data break) is dropped.
- Signals: the same indicator code as the live scan (indicators.compute_all / weekly_table) and the
  same rules as screener._screen_bars, evaluated for every day. A random sample of days is
  re-checked against screener.screen_stock itself and the mismatch count is reported.
- Outcome: forward return over 5 / 20 / 60 trading days from the signal day's close, and the
  excess return over the equal-weight average of all universe stocks on the same day
  (removes the market's own move, so a signal is not credited for a bull market).
- t-stats: per-date mean excess return, Newey-West with lag = horizon (events cluster on the same
  days and long horizons overlap, so a naive per-event t-stat would be far too optimistic).
"""
import argparse
import datetime
import json
import math
import os
import random
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from src import indicators, screener
from src.fetch_data import FINMIND_URL, RateLimiter

HORIZONS = (5, 20, 60)
ROUND_TRIP_COST = 0.00585  # 0.1425% fee x2 + 0.3% transaction tax

DAILY_CODES = [
    "ma_golden_cross", "ma_death_cross", "macd_golden_cross", "macd_death_cross",
    "bb_breakout_upper", "bb_breakout_lower", "new_high", "new_low",
    "rsi_overbought", "rsi_oversold", "volume_spike",
    "close_above_ma20", "close_below_ma20", "close_above_ma5", "close_below_ma5",
]
WEEKLY_CODES = ["wma_golden_cross", "wma_death_cross", "w_rsi_overbought", "w_rsi_oversold",
                "w_macd_golden_cross", "w_macd_death_cross", "w_new_high", "w_new_low"]
COMBOS = {
    "rsi_oversold+new_low": ("rsi_oversold", "new_low", True),
    "rsi_oversold_only": ("rsi_oversold", "new_low", False),
    "rsi_overbought+new_high": ("rsi_overbought", "new_high", True),
    "rsi_overbought_only": ("rsi_overbought", "new_high", False),
}
BEARISH = {"ma_death_cross", "macd_death_cross", "bb_breakout_lower", "new_low"}
BULLISH = {"ma_golden_cross", "macd_golden_cross", "bb_breakout_upper", "new_high"}


# ---------------------------------------------------------------- data
def _get(dataset: str, stock_id: str, start: str, end: str, token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start, "end_date": end}
    for attempt in range(3):
        try:
            r = requests.get(FINMIND_URL, params=params, headers=headers, timeout=60)
            r.raise_for_status()
            p = r.json()
            if p.get("status") != 200:
                raise RuntimeError(p.get("msg"))
            return p.get("data", [])
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    return []


def _rows(data: list[dict]) -> list[tuple]:
    out = []
    for d in data:
        c = d.get("close")
        if c is None or c <= 0:
            continue
        out.append((d["date"], d.get("open"), d.get("max"), d.get("min"), c, d.get("Trading_Volume")))
    return out


def load_prices(universe, start, end, db_path, token, rph, log):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS px (stock_id TEXT, date TEXT, open REAL, high REAL, low REAL,"
                 " close REAL, volume REAL, PRIMARY KEY (stock_id, date))")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    got = dict(conn.execute("SELECT k, v FROM meta").fetchall())
    source = got.get("source")
    limiter = RateLimiter(rph)
    if source is None:
        limiter.wait()
        try:
            probe = _get("TaiwanStockPriceAdj", "2330", "2024-01-01", "2024-02-01", token)
            source = "TaiwanStockPriceAdj" if probe else "TaiwanStockPrice"
        except Exception as e:  # noqa: BLE001
            log(f"adjusted prices unavailable ({e}); using raw prices")
            source = "TaiwanStockPrice"
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('source', ?)", (source,))
        conn.commit()
    log(f"price source: {source}")
    failed = []
    for i, s in enumerate(universe):
        sid = s["stock_id"]
        last = conn.execute("SELECT MAX(date) FROM px WHERE stock_id=?", (sid,)).fetchone()[0]
        if last and last >= (datetime.date.fromisoformat(end) - datetime.timedelta(days=4)).isoformat():
            continue
        limiter.wait()
        try:
            data = _get(source, sid, start, end, token)
        except Exception as e:  # noqa: BLE001
            failed.append(sid)
            log(f"  {sid} failed: {e}")
            continue
        conn.executemany("INSERT OR REPLACE INTO px VALUES (?,?,?,?,?,?,?)", [(sid, *r) for r in _rows(data)])
        conn.commit()
        if (i + 1) % 20 == 0:
            log(f"  fetched {i + 1}/{len(universe)}")
    return conn, source, failed


# ---------------------------------------------------------------- signals
def daily_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Vectorised copy of screener._screen_bars (daily) + _price_ma_crosses. One bool column per code."""
    t, y = df, df.shift(1)
    out = pd.DataFrame(index=df.index)
    f, s = f"ma{cfg['ma_cross_fast']}", f"ma{cfg['ma_cross_slow']}"
    ok = t[f].notna() & t[s].notna() & y[f].notna() & y[s].notna()
    g = ok & (y[f] <= y[s]) & (t[f] > t[s])
    out["ma_golden_cross"] = g
    out["ma_death_cross"] = ok & ~g & (y[f] >= y[s]) & (t[f] < t[s])
    ob = t["rsi"].notna() & (t["rsi"] >= cfg["rsi_overbought"])
    out["rsi_overbought"] = ob
    out["rsi_oversold"] = t["rsi"].notna() & ~ob & (t["rsi"] <= cfg["rsi_oversold"])
    ok = t["macd"].notna() & t["macd_signal"].notna() & y["macd"].notna() & y["macd_signal"].notna()
    g = ok & (y["macd"] <= y["macd_signal"]) & (t["macd"] > t["macd_signal"])
    out["macd_golden_cross"] = g
    out["macd_death_cross"] = ok & ~g & (y["macd"] >= y["macd_signal"]) & (t["macd"] < t["macd_signal"])
    up = t["bb_upper"].notna() & (t["close"] > t["bb_upper"])
    out["bb_breakout_upper"] = up
    out["bb_breakout_lower"] = ~up & t["bb_lower"].notna() & (t["close"] < t["bb_lower"])
    va = t["vol_avg"]
    out["volume_spike"] = va.notna() & (va > 0) & (t["volume"] / va.where(va > 0) >= cfg["volume_spike_multiplier"])
    nh = t["roll_high"].notna() & (t["close"] >= t["roll_high"])
    out["new_high"] = nh
    out["new_low"] = ~nh & t["roll_low"].notna() & (t["close"] <= t["roll_low"])
    for p in screener.PRICE_MA_PERIODS:
        c = f"ma{p}"
        ok = t["close"].notna() & t[c].notna() & y["close"].notna() & y[c].notna()
        a = ok & (y["close"] <= y[c]) & (t["close"] > t[c])
        out[f"close_above_ma{p}"] = a
        out[f"close_below_ma{p}"] = ok & ~a & (y["close"] >= y[c]) & (t["close"] < t[c])
    out.iloc[0] = False
    return out.fillna(False).astype(bool)


def weekly_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Weekly rules on completed weeks; the event day is the week's last trading day."""
    wk = indicators.weekly_table(df[["date", "close", "volume"]].copy(), cfg)
    if len(wk) and datetime.date.fromisoformat(wk.iloc[-1]["last_date"]).weekday() != 4:
        wk = wk.iloc[:-1]  # in-progress week
    t, y = wk, wk.shift(1)
    out = pd.DataFrame(index=wk.index)
    f, s = f"wma{cfg.get('weekly_ma_fast', 5)}", f"wma{cfg.get('weekly_ma_slow', 20)}"
    ok = t[f].notna() & t[s].notna() & y[f].notna() & y[s].notna()
    g = ok & (y[f] <= y[s]) & (t[f] > t[s])
    out["wma_golden_cross"] = g
    out["wma_death_cross"] = ok & ~g & (y[f] >= y[s]) & (t[f] < t[s])
    ob = t["rsi"].notna() & (t["rsi"] >= cfg["rsi_overbought"])
    out["w_rsi_overbought"] = ob
    out["w_rsi_oversold"] = t["rsi"].notna() & ~ob & (t["rsi"] <= cfg["rsi_oversold"])
    ok = t["macd"].notna() & t["macd_signal"].notna() & y["macd"].notna() & y["macd_signal"].notna()
    g = ok & (y["macd"] <= y["macd_signal"]) & (t["macd"] > t["macd_signal"])
    out["w_macd_golden_cross"] = g
    out["w_macd_death_cross"] = ok & ~g & (y["macd"] >= y["macd_signal"]) & (t["macd"] < t["macd_signal"])
    nh = t["roll_high"].notna() & (t["close"] >= t["roll_high"])
    out["w_new_high"] = nh
    out["w_new_low"] = ~nh & t["roll_low"].notna() & (t["close"] <= t["roll_low"])
    if len(out):
        out.iloc[0] = False
    out = out.fillna(False).astype(bool)
    out["date"] = wk["last_date"].values
    return out


def verify_against_screener(df: pd.DataFrame, sig: pd.DataFrame, cfg: dict, n: int, rng: random.Random) -> tuple[int, int]:
    idx = list(range(80, len(df)))
    bad = 0
    picks = rng.sample(idx, min(n, len(idx)))
    for i in picks:
        live = {a["signal"] for a in screener.screen_stock(df.iloc[: i + 1], cfg)}
        mine = {c for c in DAILY_CODES if sig.at[i, c]}
        if live != mine:
            bad += 1
    return bad, len(picks)


# ---------------------------------------------------------------- stats
def nw_t(x: np.ndarray, lag: int) -> float:
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 10:
        return float("nan")
    e = x - x.mean()
    v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        w = 1 - k / (lag + 1)
        v += 2 * w * (e[k:] @ e[:-k]) / n
    if v <= 0:
        return float("nan")
    return float(x.mean() / math.sqrt(v / n))


def summarize(ev: pd.DataFrame, h: int) -> dict:
    col, ex = f"r{h}", f"x{h}"
    e = ev.dropna(subset=[ex])
    if len(e) == 0:
        return {"n": 0}
    per_date = e.groupby("date")[ex].mean().sort_index().to_numpy()
    return {
        "n": int(len(e)),
        "dates": int(e["date"].nunique()),
        "raw_mean": float(e[col].mean()),
        "excess_mean": float(e[ex].mean()),
        "excess_median": float(e[ex].median()),
        "hit": float((e[ex] > 0).mean()),
        "t_nw": nw_t(per_date, h),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=datetime.date.today().isoformat())
    ap.add_argument("--db", default="data/backtest.db")
    ap.add_argument("--out", default="backtest/results")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    started = time.time()
    log = lambda m: print(f"[{time.time() - started:7.1f}s] {m}", flush=True)  # noqa: E731
    cfg_path = "config/settings.yaml" if os.path.exists("config/settings.yaml") else "config/settings.ci.yaml"
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    ind = cfg["indicators"]
    token = os.environ.get("FINMIND_TOKEN", "") or cfg.get("finmind", {}).get("token", "")
    rph = 550 if token else cfg.get("finmind", {}).get("requests_per_hour", 280)
    universe = json.load(open(cfg["universe_file"], encoding="utf-8"))["stocks"]
    if args.limit:
        universe = universe[: args.limit]
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn, source, failed = load_prices(universe, args.start, args.end, args.db, token, rph, log)

    rng = random.Random(7)
    events, closes = [], {}
    verify_bad = verify_n = 0
    first_dates = {}
    for k, s in enumerate(universe):
        sid = s["stock_id"]
        df = pd.read_sql_query("SELECT date, open, high, low, close, volume FROM px WHERE stock_id=? AND date>=? ORDER BY date",
                               conn, params=(sid, args.start))
        if len(df) < 130:
            continue
        first_dates[sid] = df["date"].iloc[0]
        df = indicators.compute_all(df, ind)
        sig = daily_signals(df, ind)
        if k % 6 == 0:  # spot-check the vectorised rules against the live screener
            b, n = verify_against_screener(df, sig, ind, 40, rng)
            verify_bad += b
            verify_n += n
        c = df["close"].to_numpy(float)
        ret1 = np.r_[np.nan, c[1:] / c[:-1] - 1]
        jump = np.abs(ret1) > 0.11 if source == "TaiwanStockPrice" else np.zeros(len(c), bool)
        fwd = {}
        for h in HORIZONS:
            r = np.full(len(c), np.nan)
            r[:-h] = c[h:] / c[:-h] - 1
            if jump.any():  # drop windows that contain a split / data break
                cj = np.r_[0, np.cumsum(jump)]
                bad = np.zeros(len(c), bool)
                bad[:-h] = (cj[h + 1:] - cj[1:-h]) > 0
                r[bad] = np.nan
            fwd[h] = r
        closes[sid] = pd.DataFrame({"date": df["date"], **{f"r{h}": fwd[h] for h in HORIZONS}})
        dates = df["date"].to_numpy()
        for code in DAILY_CODES:
            for i in np.flatnonzero(sig[code].to_numpy()):
                events.append((sid, dates[i], code, *[fwd[h][i] for h in HORIZONS]))
        for name, (a, b2, both) in COMBOS.items():
            m = sig[a].to_numpy() & (sig[b2].to_numpy() if both else ~sig[b2].to_numpy())
            for i in np.flatnonzero(m):
                events.append((sid, dates[i], name, *[fwd[h][i] for h in HORIZONS]))
        wsig = weekly_signals(df, ind)
        pos = {d: i for i, d in enumerate(dates)}
        for code in WEEKLY_CODES:
            for d in wsig.loc[wsig[code], "date"]:
                i = pos.get(d)
                if i is not None:
                    events.append((sid, d, code, *[fwd[h][i] for h in HORIZONS]))
        # breadth inputs
        closes[sid]["bear"] = sig[list(BEARISH)].any(axis=1).to_numpy()
        closes[sid]["bull"] = sig[list(BULLISH)].any(axis=1).to_numpy()
        closes[sid]["oversold"] = sig["rsi_oversold"].to_numpy()
    log(f"signals computed for {len(closes)} stocks; screener spot-check mismatches {verify_bad}/{verify_n}")

    panel = pd.concat([v.assign(stock_id=k) for k, v in closes.items()], ignore_index=True)
    bench = panel.groupby("date")[[f"r{h}" for h in HORIZONS]].mean()
    ev = pd.DataFrame(events, columns=["stock_id", "date", "code", *[f"r{h}" for h in HORIZONS]])
    ev = ev.join(bench, on="date", rsuffix="_b")
    for h in HORIZONS:
        ev[f"x{h}"] = ev[f"r{h}"] - ev[f"r{h}_b"]

    # market regime on each date: equal-weight universe trailing 60-day return
    px_wide = None
    panel_c = []
    for sid in closes:
        df = pd.read_sql_query("SELECT date, close FROM px WHERE stock_id=? AND date>=? ORDER BY date", conn, params=(sid, args.start))
        panel_c.append(df.set_index("date")["close"].rename(sid))
    px_wide = pd.concat(panel_c, axis=1).sort_index()
    trail = (px_wide / px_wide.shift(60) - 1).mean(axis=1)
    regime = np.where(trail > 0, "up", "down")
    regime = pd.Series(regime, index=trail.index).where(trail.notna())
    ev["regime"] = ev["date"].map(regime)
    split = "2021-01-01"

    res = {"meta": {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "start": args.start, "end": args.end, "price_source": source,
        "stocks": len(closes), "failed_fetch": failed,
        "first_dates": first_dates,
        "screener_check": {"mismatch": verify_bad, "checked": verify_n},
        "round_trip_cost": ROUND_TRIP_COST, "horizons": list(HORIZONS),
        "events": int(len(ev)), "trading_days": int(bench.shape[0]),
    }, "signals": {}}
    for code, g in ev.groupby("code"):
        row = {}
        for h in HORIZONS:
            row[str(h)] = {
                "all": summarize(g, h),
                "pre2021": summarize(g[g["date"] < split], h),
                "post2021": summarize(g[g["date"] >= split], h),
                "up": summarize(g[g["regime"] == "up"], h),
                "down": summarize(g[g["regime"] == "down"], h),
            }
        res["signals"][code] = row

    # breadth: share of stocks with a bearish / oversold signal that day -> next-period universe return
    by_day = panel.groupby("date").agg(bear=("bear", "mean"), bull=("bull", "mean"), oversold=("oversold", "mean"),
                                       **{f"r{h}": (f"r{h}", "mean") for h in HORIZONS})
    breadth = {}
    for name, col, cuts in (("bear_share", "bear", [0, .1, .2, .3, .4, 1.01]),
                            ("oversold_share", "oversold", [0, .05, .1, .2, .3, 1.01])):
        b = pd.cut(by_day[col], cuts, right=False)
        tbl = by_day.groupby(b, observed=True)[[f"r{h}" for h in HORIZONS]].agg(["mean", "count"])
        breadth[name] = [
            {"bucket": str(iv), **{f"r{h}_mean": float(tbl.loc[iv, (f"r{h}", "mean")]) for h in HORIZONS},
             "days": int(tbl.loc[iv, ("r5", "count")])}
            for iv in tbl.index
        ]
    breadth["unconditional"] = {f"r{h}_mean": float(by_day[f"r{h}"].mean()) for h in HORIZONS}
    res["breadth"] = breadth

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "summary.md").write_text(render_md(res), encoding="utf-8")
    log(f"done: {len(ev)} events -> {out}")


def render_md(res: dict) -> str:
    m = res["meta"]
    lines = [f"# Signal backtest ({m['start']} – {m['end']})", "",
             f"- price source: {m['price_source']}; stocks: {m['stocks']}; trading days: {m['trading_days']}",
             f"- screener spot-check mismatches: {m['screener_check']['mismatch']}/{m['screener_check']['checked']}",
             f"- round-trip cost: {m['round_trip_cost']:.3%}", "",
             "| signal | h | n | excess mean | median | hit | t(NW) | pre2021 | post2021 | up mkt | down mkt |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for code, row in sorted(res["signals"].items()):
        for h in m["horizons"]:
            a = row[str(h)]
            if not a["all"].get("n"):
                continue
            f = lambda d: f"{d['excess_mean']:+.2%}" if d.get("n") else "—"  # noqa: E731
            al = a["all"]
            lines.append(f"| {code} | {h} | {al['n']} | {al['excess_mean']:+.2%} | {al['excess_median']:+.2%} | "
                         f"{al['hit']:.1%} | {al['t_nw']:.2f} | {f(a['pre2021'])} | {f(a['post2021'])} | {f(a['up'])} | {f(a['down'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
