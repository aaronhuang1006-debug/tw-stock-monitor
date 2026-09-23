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
}


def screen_stock(df: pd.DataFrame, cfg: dict) -> list[dict]:
    if len(df) < 2:
        return []
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    signals = []

    fast, slow = cfg["ma_cross_fast"], cfg["ma_cross_slow"]
    ma_fast_col, ma_slow_col = f"ma{fast}", f"ma{slow}"
    if pd.notna(today[ma_fast_col]) and pd.notna(today[ma_slow_col]) and pd.notna(yesterday[ma_fast_col]) and pd.notna(yesterday[ma_slow_col]):
        if yesterday[ma_fast_col] <= yesterday[ma_slow_col] and today[ma_fast_col] > today[ma_slow_col]:
            signals.append(("ma_golden_cross", SIGNAL_LABELS["ma_golden_cross"].format(fast=fast, slow=slow)))
        elif yesterday[ma_fast_col] >= yesterday[ma_slow_col] and today[ma_fast_col] < today[ma_slow_col]:
            signals.append(("ma_death_cross", SIGNAL_LABELS["ma_death_cross"].format(fast=fast, slow=slow)))

    if pd.notna(today["rsi"]):
        if today["rsi"] >= cfg["rsi_overbought"]:
            signals.append(("rsi_overbought", SIGNAL_LABELS["rsi_overbought"].format(rsi=today["rsi"])))
        elif today["rsi"] <= cfg["rsi_oversold"]:
            signals.append(("rsi_oversold", SIGNAL_LABELS["rsi_oversold"].format(rsi=today["rsi"])))

    if pd.notna(today["macd"]) and pd.notna(today["macd_signal"]) and pd.notna(yesterday["macd"]) and pd.notna(yesterday["macd_signal"]):
        if yesterday["macd"] <= yesterday["macd_signal"] and today["macd"] > today["macd_signal"]:
            signals.append(("macd_golden_cross", SIGNAL_LABELS["macd_golden_cross"]))
        elif yesterday["macd"] >= yesterday["macd_signal"] and today["macd"] < today["macd_signal"]:
            signals.append(("macd_death_cross", SIGNAL_LABELS["macd_death_cross"]))

    if pd.notna(today["bb_upper"]) and today["close"] > today["bb_upper"]:
        signals.append(("bb_breakout_upper", SIGNAL_LABELS["bb_breakout_upper"]))
    elif pd.notna(today["bb_lower"]) and today["close"] < today["bb_lower"]:
        signals.append(("bb_breakout_lower", SIGNAL_LABELS["bb_breakout_lower"]))

    vol_period = cfg["volume_avg_period"]
    mult_thresh = cfg["volume_spike_multiplier"]
    if pd.notna(today["vol_avg"]) and today["vol_avg"] > 0:
        mult = today["volume"] / today["vol_avg"]
        if mult >= mult_thresh:
            signals.append(("volume_spike", SIGNAL_LABELS["volume_spike"].format(mult=mult, period=vol_period)))

    nh_period = cfg["new_high_low_period"]
    if pd.notna(today["roll_high"]) and today["close"] >= today["roll_high"]:
        signals.append(("new_high", SIGNAL_LABELS["new_high"].format(period=nh_period)))
    elif pd.notna(today["roll_low"]) and today["close"] <= today["roll_low"]:
        signals.append(("new_low", SIGNAL_LABELS["new_low"].format(period=nh_period)))

    return [{"signal": code, "detail": label} for code, label in signals]
