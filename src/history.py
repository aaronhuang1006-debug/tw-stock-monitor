"""Day-by-day signal history, kept as a small JSON file next to the published page.

The Actions cache that holds data/stock.db is not durable or visible, so the history lives in
docs/history.json and is committed with the page. Each day stores which stocks fired which signals
(codes are indices into an append-only `codes` list to keep the file small).

Because every indicator is derived from daily prices, past days can be rebuilt from the price
database; `replay_missing` does that on the first run and whenever a day was skipped.
"""
import datetime
import json
from pathlib import Path

import pandas as pd

from . import db, indicators, screener


def load(path: Path) -> dict:
    if path.exists():
        try:
            hist = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(hist.get("codes"), list) and isinstance(hist.get("days"), list):
                return hist
        except (ValueError, OSError):
            pass
    return {"version": 1, "codes": [], "days": []}


def save(path: Path, hist: dict) -> None:
    hist["days"].sort(key=lambda day: day["d"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _code_index(hist: dict, code: str) -> int:
    if code not in hist["codes"]:
        hist["codes"].append(code)
    return hist["codes"].index(code)


def put_day(hist: dict, date: str, evaluated: int, signals_by_stock: dict[str, list[str]]) -> None:
    record = {
        "d": date,
        "n": evaluated,
        "s": {sid: [_code_index(hist, c) for c in codes] for sid, codes in signals_by_stock.items() if codes},
    }
    hist["days"] = [day for day in hist["days"] if day["d"] != date] + [record]


def put_day_from_alerts(hist: dict, date: str, evaluated: int, alerts: list[dict]) -> None:
    by_stock: dict[str, list[str]] = {}
    for a in alerts:
        by_stock.setdefault(a["stock_id"], []).append(a["signal"])
    put_day(hist, date, evaluated, by_stock)


def trim(hist: dict, max_days: int) -> None:
    hist["days"].sort(key=lambda day: day["d"])
    hist["days"] = hist["days"][-max_days:]


def replay_missing(conn, universe: list[dict], ind_cfg: dict, hist: dict, exclude: set[str],
                   max_days: int, min_rows: int) -> int:
    """Rebuild signals for past trading days that the history doesn't have yet.

    Indicators only look backwards, so computing them once on the full series and cutting the
    frame at each day gives the same values the live run would have produced that day.
    Returns the number of days added.
    """
    frames: dict[str, pd.DataFrame] = {}
    position: dict[str, dict[str, int]] = {}
    date_counts: dict[str, int] = {}
    for stock in universe:
        df = db.load_price_history(conn, stock["stock_id"], min_rows=min_rows)
        if df is None:
            continue
        df = indicators.compute_all(df, ind_cfg)
        frames[stock["stock_id"]] = df
        position[stock["stock_id"]] = {d: i for i, d in enumerate(df["date"])}
        for d in df["date"]:
            date_counts[d] = date_counts.get(d, 0) + 1
    if not frames:
        return 0

    calendar = sorted(d for d, c in date_counts.items() if c >= len(frames) * 0.5)
    have = {day["d"] for day in hist["days"]} | set(exclude)
    targets = [d for d in calendar[min_rows:][-max_days:] if d not in have]

    for date in targets:
        weekday = datetime.date.fromisoformat(date).weekday()
        evaluated = 0
        by_stock: dict[str, list[str]] = {}
        for sid, df in frames.items():
            i = position[sid].get(date)
            if i is None or i + 1 < min_rows:
                continue
            sub = df.iloc[: i + 1]
            evaluated += 1
            signals = screener.screen_stock(sub, ind_cfg)
            # Weekly rules only fire on a Friday or on the first run of a week; skip the weekly
            # rebuild on the other days since it can't produce anything.
            new_week = i > 0 and (
                datetime.date.fromisoformat(df.iloc[i - 1]["date"]).isocalendar()[:2]
                != datetime.date.fromisoformat(date).isocalendar()[:2]
            )
            if weekday == 4 or new_week:
                weekly = indicators.weekly_table(sub, ind_cfg)
                signals += screener.screen_weekly(sub, weekly, ind_cfg)
            if signals:
                by_stock[sid] = [s["signal"] for s in signals]
        put_day(hist, date, evaluated, by_stock)
    return len(targets)


SERIES_DAYS = 120  # per-stock chart: about six months of daily bars
SERIES_COLS = ("date", "open", "high", "low", "close", "volume", "ma20", "ma60")


def _sig(val, digits: int = 4, whole: bool = True):
    """Compact number for the page payload: ~4 significant digits (enough to draw and to read off a
    price), integers without a trailing .0, None for gaps."""
    if val is None or pd.isna(val):
        return None
    val = float(val)
    if val == 0:
        return 0
    mag = len(str(int(abs(val)))) if abs(val) >= 1 else 0
    places = digits - mag if abs(val) >= 1 else digits
    out = round(val, max(0, places) if whole else places)  # whole: never round away integer digits
    return int(out) if out == int(out) else out


def build_series(tails: dict[str, pd.DataFrame], ndays: int = SERIES_DAYS, vol_unit: float = 1) -> dict:
    """Daily bars per stock for the candlestick chart, aligned on one shared date axis.

    Per stock: o/h/l/c (o/h/l to ~4 significant digits, c at full 2-decimal precision), v (volume / vol_unit),
    m (20-day MA), q (60-day MA). Missing days are null.
    """
    all_dates = sorted({d for t in tails.values() for d in t["date"]})
    dates = all_dates[-ndays:]

    def price(val):
        return None if val is None or pd.isna(val) else (lambda r: int(r) if r == int(r) else r)(round(float(val), 2))

    values = {}
    for sid, t in tails.items():
        by_date = t.set_index("date")
        rows = [by_date.loc[d] if d in by_date.index else None for d in dates]

        def col(name, fmt):
            if name not in t.columns:
                return [None] * len(dates)
            return [None if r is None else fmt(r[name]) for r in rows]

        values[sid] = {
            "o": col("open", _sig), "h": col("high", _sig), "l": col("low", _sig), "c": col("close", price),
            "v": col("volume", lambda x: _sig(None if x is None or pd.isna(x) else float(x) / vol_unit, 3, whole=False)),
            "m": col("ma20", _sig), "q": col("ma60", _sig),
        }
    return {"dates": dates, "v": values}
