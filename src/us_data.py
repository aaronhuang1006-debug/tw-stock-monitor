"""US side: universe (Nasdaq-100 + PHLX Semiconductor) and daily prices from Yahoo Finance.

Prices are split- and dividend-adjusted (auto_adjust), downloaded for all tickers in one request
and stored in the same daily_price table layout as the Taiwan scan, so indicators, screener,
history and tracking work unchanged.
"""
import datetime
import io
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import requests

WIKI = "https://en.wikipedia.org/wiki/"
UA = {"User-Agent": "Mozilla/5.0 (tw-stock-monitor; signal board)"}

# Used only when the Wikipedia table for the semiconductor index can't be read.
SOX_FALLBACK = [
    "ADI", "ALAB", "AMAT", "AMD", "AMKR", "ARM", "ASML", "AVGO", "COHR", "CRUS", "ENTG", "GFS", "INTC",
    "KLAC", "LRCX", "LSCC", "MCHP", "MPWR", "MRVL", "MU", "NVDA", "NXPI", "ON", "ONTO", "QCOM", "SWKS",
    "TER", "TSM", "TXN", "MKSI",
]

SECTOR_ZH = {
    "Information Technology": "資訊科技", "Communication Services": "通訊服務", "Consumer Discretionary": "非必需消費",
    "Consumer Staples": "必需消費", "Health Care": "醫療保健", "Industrials": "工業", "Utilities": "公用事業",
    "Financials": "金融", "Energy": "能源", "Materials": "原物料", "Real Estate": "房地產",
}


def _tables(page: str) -> list[pd.DataFrame]:
    r = requests.get(WIKI + page, headers=UA, timeout=30)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))


def _pick(tables: list[pd.DataFrame], min_rows: int) -> pd.DataFrame | None:
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if len(t) >= min_rows and any(("ticker" in c or "symbol" in c) for c in cols):
            return t
    return None


def _col(t: pd.DataFrame, *keys: str) -> str | None:
    for c in t.columns:
        if any(k in str(c).lower() for k in keys):
            return c
    return None


def _industry(sector: str, sub: str) -> str:
    sub = sub or ""
    if "Semiconductor Materials" in sub or "Semiconductor Equipment" in sub:
        return "半導體設備"
    if "Semiconductor" in sub:
        return "半導體"
    if "Software" in sub:
        return "軟體"
    return SECTOR_ZH.get(sector, sector or "其他")


def refresh_universe(path: Path) -> list[dict]:
    """Nasdaq-100 components plus the PHLX Semiconductor index, from Wikipedia; keeps the old file on failure."""
    old = json.loads(path.read_text(encoding="utf-8"))["stocks"] if path.exists() else []
    try:
        ndx = _pick(_tables("Nasdaq-100"), 90)
        if ndx is None:
            raise RuntimeError("Nasdaq-100 components table not found")
        tk, nm = _col(ndx, "ticker", "symbol"), _col(ndx, "company", "security")
        sec, sub = _col(ndx, "gics sector", "sector"), _col(ndx, "sub-industry", "industry")
        stocks = {}
        for _, r in ndx.iterrows():
            t = str(r[tk]).strip().replace(".", "-")
            stocks[t] = {"stock_id": t, "name": str(r[nm]).strip(), "index": ["NDX"],
                         "industry": _industry(str(r[sec]) if sec else "", str(r[sub]) if sub else "")}
        try:
            sox = _pick(_tables("PHLX_Semiconductor_Index"), 20)
            sox_t = [str(x).strip().replace(".", "-") for x in sox[_col(sox, "ticker", "symbol")]] if sox is not None else []
            sox_names = dict(zip(sox_t, sox[_col(sox, "company", "name")])) if sox is not None and _col(sox, "company", "name") else {}
        except Exception:  # noqa: BLE001
            sox_t, sox_names = [], {}
        if len(sox_t) < 20:
            sox_t = SOX_FALLBACK
        for t in sox_t:
            if t in stocks:
                stocks[t]["index"].append("SOX")
            else:
                stocks[t] = {"stock_id": t, "name": str(sox_names.get(t, t)), "index": ["SOX"], "industry": "半導體"}
        out = sorted(stocks.values(), key=lambda s: s["stock_id"])
        if len(out) < 90:
            raise RuntimeError(f"only {len(out)} tickers")
        path.write_text(json.dumps({"updated": datetime.date.today().isoformat(), "stocks": out},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"[us-universe] refresh failed, keeping previous list: {exc}", file=sys.stderr)
        return old


def download(conn: sqlite3.Connection, tickers: list[str], start: str) -> dict:
    """One bulk Yahoo request; upserts adjusted OHLCV. Returns counts."""
    import yfinance as yf

    data = yf.download(tickers, start=start, auto_adjust=True, group_by="ticker", threads=True,
                       progress=False)
    ok, missing = 0, []
    rows = []
    for t in tickers:
        try:
            d = data[t].dropna(subset=["Close"])
        except KeyError:
            missing.append(t)
            continue
        if d.empty:
            missing.append(t)
            continue
        ok += 1
        for idx, r in d.iterrows():
            rows.append((t, idx.strftime("%Y-%m-%d"), float(r["Open"]), float(r["High"]), float(r["Low"]),
                         float(r["Close"]), float(r["Volume"]) if pd.notna(r["Volume"]) else None))
    conn.executemany(
        "INSERT OR REPLACE INTO daily_price (stock_id, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    return {"ok": ok, "missing": missing, "rows": len(rows)}
