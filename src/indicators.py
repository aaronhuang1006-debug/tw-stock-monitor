import pandas as pd


def add_moving_averages(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    for p in periods:
        df[f"ma{p}"] = df["close"].rolling(p).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int) -> pd.DataFrame:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))
    df.loc[avg_loss == 0, "rsi"] = 100
    return df


def add_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def add_bollinger(df: pd.DataFrame, period: int, std_mult: float) -> pd.DataFrame:
    mid = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    df["bb_mid"] = mid
    df["bb_upper"] = mid + std_mult * std
    df["bb_lower"] = mid - std_mult * std
    return df


def add_volume_avg(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df["vol_avg"] = df["volume"].shift(1).rolling(period).mean()
    return df


def add_rolling_extreme(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df["roll_high"] = df["close"].rolling(period).max()
    df["roll_low"] = df["close"].rolling(period).min()
    return df


def latest_snapshot(df: pd.DataFrame) -> dict:
    """Today's indicator values regardless of whether any signal fired — used for on-demand stock lookup."""
    last = df.iloc[-1]

    def r(val, nd=2):
        return round(float(val), nd) if pd.notna(val) else None

    vol_ratio = None
    if pd.notna(last.get("vol_avg")) and last.get("vol_avg"):
        vol_ratio = round(float(last["volume"]) / float(last["vol_avg"]), 2)

    return {
        "close": r(last["close"]),
        "ma5": r(last.get("ma5")),
        "ma20": r(last.get("ma20")),
        "ma60": r(last.get("ma60")),
        "rsi": r(last.get("rsi"), 1),
        "macd": r(last.get("macd")),
        "macd_signal": r(last.get("macd_signal")),
        "bb_upper": r(last.get("bb_upper")),
        "bb_mid": r(last.get("bb_mid")),
        "bb_lower": r(last.get("bb_lower")),
        "volume": int(last["volume"]) if pd.notna(last["volume"]) else None,
        "vol_ratio": vol_ratio,
    }


def compute_all(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)
    df = add_moving_averages(df, cfg["ma_periods"])
    df = add_rsi(df, cfg["rsi_period"])
    df = add_macd(df, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"])
    df = add_bollinger(df, cfg["bollinger_period"], cfg["bollinger_std"])
    df = add_volume_avg(df, cfg["volume_avg_period"])
    df = add_rolling_extreme(df, cfg["new_high_low_period"])
    return df
