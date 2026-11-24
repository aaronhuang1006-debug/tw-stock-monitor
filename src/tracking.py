"""Live tracking: how the signals the board actually showed went on to perform.

The backtest (src/backtest.py) re-derives ten years of signals; this module instead keeps every day's
real signals in docs/track_log.json (same compact format as history.json, but never trimmed) and,
on each daily run, measures what happened afterwards with the prices in data/stock.db:

- forward return over 5 / 20 / 60 trading days from the signal day's close,
- excess return over the equal-weight average of the universe over the same window,
- windows that contain a one-day move beyond ±11% (split / data break) are dropped.

Results go to docs/tracking.json and onto the board. Signals whose window has not finished yet are
counted as pending, so 60-day numbers only appear about three months after a signal.
"""
import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import history

HORIZONS = (5, 20, 60)

# Groups shown on the board (label, codes); codes not listed still get their own row in the JSON.
GROUPS = [
    ("強勢延續", ["w_new_high", "new_high", "w_rsi_overbought", "rsi_overbought", "w_bb_breakout_upper", "bb_breakout_upper"]),
    ("弱勢延續", ["w_new_low", "new_low", "w_rsi_oversold", "rsi_oversold", "w_bb_breakout_lower", "bb_breakout_lower"]),
    ("RSI超買", ["rsi_overbought"]),
    ("RSI超賣", ["rsi_oversold"]),
    ("創60日新高", ["new_high"]),
    ("創60日新低", ["new_low"]),
    ("月線負乖離≥25%", ["bias_neg_25", "bias_neg_35"]),
    ("月線正乖離≥25%", ["bias_pos_25", "bias_pos_35"]),
    ("成交量異常", ["volume_spike"]),
    ("週線死亡交叉", ["wma_death_cross"]),
    ("週線黃金交叉", ["wma_golden_cross"]),
    ("交叉(參考)", ["ma_golden_cross", "ma_death_cross", "macd_golden_cross", "macd_death_cross"]),
]


def load_log(path: Path, seed: dict | None = None) -> dict:
    """The permanent signal log; the first time, it starts from whatever history.json still holds."""
    log = history.load(path)
    if not log["days"] and seed and seed.get("days"):
        log = json.loads(json.dumps(seed))
        log["seeded_from_history"] = True
    return log


def record_day(log: dict, date: str, evaluated: int, alerts: list[dict]) -> None:
    history.put_day_from_alerts(log, date, evaluated, alerts)


def save_log(path: Path, log: dict) -> None:
    history.save(path, log)


def _closes(conn, stock_ids: list[str], start: str) -> pd.DataFrame:
    q = f"SELECT stock_id, date, close FROM daily_price WHERE date >= ? AND stock_id IN ({','.join('?' * len(stock_ids))})"
    df = pd.read_sql_query(q, conn, params=[start, *stock_ids])
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index="date", columns="stock_id", values="close").sort_index()


def _stats(x: np.ndarray, dates: list[str] | None = None) -> dict:
    keep = ~np.isnan(x)
    x = x[keep]
    if not len(x):
        return {"n": 0}
    out = {"n": int(len(x)), "mean": round(float(x.mean()), 5), "median": round(float(np.median(x)), 5),
           "hit": round(float((x > 0).mean()), 4)}
    if dates is not None:  # how many different trading days the signals came from (they cluster)
        out["dates"] = len({d for d, k in zip(dates, keep) if k})
    return out


def compute(conn, log: dict, stock_ids: list[str], backtest_path: Path | None = None) -> dict:
    days = sorted(log["days"], key=lambda d: d["d"])
    if not days:
        return {}
    start = days[0]["d"]
    px = _closes(conn, stock_ids, (datetime.date.fromisoformat(start) - datetime.timedelta(days=10)).isoformat())
    if px.empty:
        return {}
    ret1 = px / px.shift(1) - 1
    jump = (ret1.abs() > 0.11).astype(float)
    fwd, exc = {}, {}
    for h in HORIZONS:
        r = px.shift(-h) / px - 1
        # a split/data break inside (t, t+h] voids the window
        broken = jump[::-1].rolling(h, min_periods=1).sum()[::-1].shift(-1).fillna(0) > 0
        r = r.mask(broken)
        fwd[h] = r
        exc[h] = r.sub(r.mean(axis=1), axis=0)

    codes = log["codes"]
    rows = {c: {h: [] for h in HORIZONS} for c in codes}
    pending = {c: 0 for c in codes}
    fired = {c: 0 for c in codes}
    date_index = {d: i for i, d in enumerate(px.index)}
    for day in days:
        d = day["d"]
        if d not in date_index:
            continue
        for sid, idxs in day["s"].items():
            if sid not in px.columns:
                continue
            for i in idxs:
                c = codes[i]
                fired[c] += 1
                done = False
                for h in HORIZONS:
                    v = exc[h].at[d, sid]
                    if pd.notna(v):
                        rows[c][h].append((float(v), d))
                        done = True
                if not done:
                    pending[c] += 1

    def block(code_list: list[str]) -> dict:
        out = {"fired": sum(fired.get(c, 0) for c in code_list)}
        for h in HORIZONS:
            pairs = [p for c in code_list for p in rows.get(c, {}).get(h, [])]
            out[str(h)] = _stats(np.array([v for v, _ in pairs], dtype=float), [d for _, d in pairs])
        return out

    expect = {}
    if backtest_path and backtest_path.exists():
        try:
            bt = json.loads(backtest_path.read_text(encoding="utf-8"))["signals"]
            for label, cl in GROUPS:
                vals = [bt[c]["60"]["all"] for c in cl if c in bt and bt[c]["60"]["all"].get("n")]
                if vals:  # event-weighted average of the backtest's 60-day excess means
                    n = sum(v["n"] for v in vals)
                    expect[label] = round(sum(v["excess_mean"] * v["n"] for v in vals) / n, 5)
        except (KeyError, ValueError, OSError):
            pass

    return {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "since": start,
        "last": days[-1]["d"],
        "seeded_from_history": bool(log.get("seeded_from_history")),
        "groups": [{"label": label, "codes": cl, **block(cl), "backtest60": expect.get(label)} for label, cl in GROUPS],
        "codes": {c: block([c]) for c in codes},
    }
