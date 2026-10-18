import datetime

import pandas as pd

SIGNAL_LABELS = {
    "ma_golden_cross": "均線黃金交叉(MA{fast}>MA{slow})",
    "ma_death_cross": "均線死亡交叉(MA{fast}<MA{slow})",
    "rsi_overbought": "RSI超買({rsi:.1f})",
    "rsi_oversold": "RSI超賣({rsi:.1f})",
    "macd_golden_cross": "MACD金叉",
    "macd_death_cross": "MACD死叉",
    "bb_breakout_upper": "突破布林上軌",
    "bb_breakout_lower": "跌破布林下軌",
    "volume_spike": "成交量異常放大({mult:.1f}倍於{period}日均量)",
    "new_high": "創{period}日新高",
    "new_low": "創{period}日新低",
    "wma_golden_cross": "週線黃金交叉({fast}週線>{slow}週線)",
    "wma_death_cross": "週線死亡交叉({fast}週線<{slow}週線)",
    "w_rsi_overbought": "週RSI超買({rsi:.1f})",
    "w_rsi_oversold": "週RSI超賣({rsi:.1f})",
    "w_macd_golden_cross": "週MACD金叉",
    "w_macd_death_cross": "週MACD死叉",
    "w_bb_breakout_upper": "週線突破布林上軌",
    "w_bb_breakout_lower": "週線跌破布林下軌",
    "w_volume_spike": "週量異常放大({mult:.1f}倍於{period}週均量)",
    "w_new_high": "創{period}週新高",
    "w_new_low": "創{period}週新低",
}


def _screen_bars(today, yesterday, cfg: dict, prefix: str, fast_col: str, slow_col: str,
                 cross_codes: tuple[str, str], cross_fmt: dict, nh_period: int) -> list[tuple[str, str]]:
    """The shared indicator rules, applied to one bar vs the one before it (daily or weekly)."""
    signals = []

    def add(code, **fmt):
        signals.append((code, SIGNAL_LABELS[code].format(**fmt)))

    if all(pd.notna(v) for v in (today[fast_col], today[slow_col], yesterday[fast_col], yesterday[slow_col])):
        if yesterday[fast_col] <= yesterday[slow_col] and today[fast_col] > today[slow_col]:
            add(cross_codes[0], **cross_fmt)
        elif yesterday[fast_col] >= yesterday[slow_col] and today[fast_col] < today[slow_col]:
            add(cross_codes[1], **cross_fmt)

    if pd.notna(today["rsi"]):
        if today["rsi"] >= cfg["rsi_overbought"]:
            add(f"{prefix}rsi_overbought", rsi=today["rsi"])
        elif today["rsi"] <= cfg["rsi_oversold"]:
            add(f"{prefix}rsi_oversold", rsi=today["rsi"])

    if all(pd.notna(v) for v in (today["macd"], today["macd_signal"], yesterday["macd"], yesterday["macd_signal"])):
        if yesterday["macd"] <= yesterday["macd_signal"] and today["macd"] > today["macd_signal"]:
            add(f"{prefix}macd_golden_cross")
        elif yesterday["macd"] >= yesterday["macd_signal"] and today["macd"] < today["macd_signal"]:
            add(f"{prefix}macd_death_cross")

    if pd.notna(today["bb_upper"]) and today["close"] > today["bb_upper"]:
        add(f"{prefix}bb_breakout_upper")
    elif pd.notna(today["bb_lower"]) and today["close"] < today["bb_lower"]:
        add(f"{prefix}bb_breakout_lower")

    if pd.notna(today["vol_avg"]) and today["vol_avg"] > 0:
        mult = today["volume"] / today["vol_avg"]
        if mult >= cfg["volume_spike_multiplier"]:
            add(f"{prefix}volume_spike", mult=mult, period=cfg["volume_avg_period"])

    if pd.notna(today["roll_high"]) and today["close"] >= today["roll_high"]:
        add(f"{prefix}new_high", period=nh_period)
    elif pd.notna(today["roll_low"]) and today["close"] <= today["roll_low"]:
        add(f"{prefix}new_low", period=nh_period)

    return signals


def screen_stock(df: pd.DataFrame, cfg: dict) -> list[dict]:
    if len(df) < 2:
        return []
    fast, slow = cfg["ma_cross_fast"], cfg["ma_cross_slow"]
    signals = _screen_bars(
        df.iloc[-1], df.iloc[-2], cfg, "", f"ma{fast}", f"ma{slow}",
        ("ma_golden_cross", "ma_death_cross"), {"fast": fast, "slow": slow}, cfg["new_high_low_period"],
    )
    return [{"signal": code, "detail": label} for code, label in signals]


def screen_weekly(df: pd.DataFrame, weekly: pd.DataFrame, cfg: dict) -> list[dict]:
    """The daily indicator rules applied to weekly bars, judged on completed weeks only so a
    mid-week wobble can't fire them.

    A week counts as complete on its Friday run; if Friday was a holiday the week is judged on the
    first run of the following week instead (and only then, so each signal is reported once).
    """
    fast, slow = cfg.get("weekly_ma_fast", 5), cfg.get("weekly_ma_slow", 20)
    today = df.iloc[-1]["date"]
    if datetime.date.fromisoformat(today).weekday() == 4:
        idx = len(weekly) - 1
    elif (
        len(weekly) >= 2
        and weekly.iloc[-1]["first_date"] == today
        and datetime.date.fromisoformat(weekly.iloc[-2]["last_date"]).weekday() != 4
    ):
        idx = len(weekly) - 2
    else:
        return []
    if idx < 1:
        return []

    signals = _screen_bars(
        weekly.iloc[idx], weekly.iloc[idx - 1], cfg, "w_", f"wma{fast}", f"wma{slow}",
        ("wma_golden_cross", "wma_death_cross"), {"fast": fast, "slow": slow},
        cfg.get("weekly_new_high_low_period", cfg["new_high_low_period"]),
    )
    return [{"signal": code, "detail": label} for code, label in signals]
