"""Market breadth: how many stocks are above their 20-/60-day averages, and whether the index's
large caps or the average stock are leading. Read before individual signals: the same RSI-oversold
reading means something different when 80% of stocks are above their 60-day line than when 20% are.

Everything is computed from closes already in daily_price (no extra requests), except the benchmark
(0050 for Taiwan, QQQ for the US), which the caller passes in as a date -> close series.
"""
import pandas as pd


def _pivot(conn, stock_ids: list[str], end_date: str, ndays: int = 260) -> pd.DataFrame:
    q = (f"SELECT stock_id, date, close FROM daily_price WHERE date <= ? AND stock_id IN "
         f"({','.join('?' * len(stock_ids))})")
    df = pd.read_sql_query(q, conn, params=[end_date, *stock_ids])
    if df.empty:
        return pd.DataFrame()
    px = df.pivot_table(index="date", columns="stock_id", values="close").sort_index()
    return px.tail(ndays)


def compute(conn, stock_ids: list[str], end_date: str, bench: pd.Series | None = None,
            bench_name: str = "", series_days: int = 60) -> dict:
    px = _pivot(conn, stock_ids, end_date)
    if px.empty or len(px) < 70:
        return {}
    ma20, ma60 = px.rolling(20).mean(), px.rolling(60).mean()
    valid20, valid60 = px.notna() & ma20.notna(), px.notna() & ma60.notna()
    above20 = ((px > ma20) & valid20).sum(axis=1) / valid20.sum(axis=1)
    above60 = ((px > ma60) & valid60).sum(axis=1) / valid60.sum(axis=1)
    tail = px.index[-series_days:]

    def at(s: pd.Series, back: int) -> float | None:
        return round(float(s.iloc[-1 - back]), 4) if len(s) > back and pd.notna(s.iloc[-1 - back]) else None

    out = {
        "date": px.index[-1],
        "n": int(px.iloc[-1].notna().sum()),
        "above20": at(above20, 0), "above20_prev": at(above20, 20),
        "above60": at(above60, 0), "above60_prev": at(above60, 20),
        "series": {"dates": list(tail), "above20": [round(float(v), 4) for v in above20.loc[tail]],
                   "above60": [round(float(v), 4) for v in above60.loc[tail]]},
    }
    # the typical stock (median, robust to split/data breaks in raw prices) vs the cap-weighted
    # benchmark over the last 20 trading days
    r20 = (px.iloc[-1] / px.iloc[-21] - 1).dropna()
    out["med20"] = round(float(r20.median()), 4)
    if bench is not None and not bench.empty:
        b = bench.sort_index()
        b = b[b.index <= end_date]
        jumps = (b / b.shift(1) - 1).abs().iloc[-20:] > 0.25  # split inside the window: skip, don't mislead
        if len(b) > 20 and not jumps.any():
            out["bench20"] = round(float(b.iloc[-1] / b.iloc[-21] - 1), 4)
            out["bench_name"] = bench_name
    return out
