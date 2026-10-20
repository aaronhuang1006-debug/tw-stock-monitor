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


def build_series(tails: dict[str, pd.DataFrame], ndays: int = 60) -> dict:
    """Last `ndays` closes and 20-day MAs per stock, aligned on one shared date axis."""
    all_dates = sorted({d for t in tails.values() for d in t["date"]})
    dates = all_dates[-ndays:]

    def num(val):
        return round(float(val), 2) if pd.notna(val) else None

    values = {}
    for sid, t in tails.items():
        by_date = t.set_index("date")
        closes, mas = [], []
        for d in dates:
            if d in by_date.index:
                closes.append(num(by_date.at[d, "close"]))
                mas.append(num(by_date.at[d, "ma20"]))
            else:
                closes.append(None)
                mas.append(None)
        values[sid] = {"c": closes, "m": mas}
    return {"dates": dates, "v": values}
