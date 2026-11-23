"""US side: universe (Nasdaq-100 + PHLX Semiconductor, kept in config/universe_us.json) and daily prices from Yahoo Finance.

Prices are split- and dividend-adjusted (auto_adjust), downloaded for all tickers in one request
and stored in the same daily_price table layout as the Taiwan scan, so indicators, screener,
history and tracking work unchanged.
"""
import datetime
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


# PHLX Semiconductor members (maintained list; the index publishes no free machine-readable file).
SOX_FALLBACK = [
    "ADI", "ALAB", "AMAT", "AMD", "AMKR", "ARM", "ASML", "AVGO", "COHR", "CRUS", "ENTG", "GFS", "INTC",
    "KLAC", "LRCX", "LSCC", "MCHP", "MPWR", "MRVL", "MU", "NVDA", "NXPI", "ON", "ONTO", "QCOM", "SWKS",
    "TER", "TSM", "TXN", "MKSI",
]

YAHOO_SECTOR_ZH = {
    "Technology": "資訊科技", "Communication Services": "通訊服務", "Consumer Cyclical": "非必需消費",
    "Consumer Defensive": "必需消費", "Healthcare": "醫療保健", "Industrials": "工業", "Utilities": "公用事業",
    "Financial Services": "金融", "Energy": "能源", "Basic Materials": "原物料", "Real Estate": "房地產",
}


def _yahoo_industry(sector: str, industry: str) -> str:
    if "Semiconductor Equipment" in industry:
        return "半導體設備"
    if "Semiconductor" in industry:
        return "半導體"
    if "Software" in industry:
        return "軟體"
    return YAHOO_SECTOR_ZH.get(sector, sector or "其他")


def refresh_universe(path: Path) -> list[dict]:
    """config/universe_us.json holds the membership (kept by hand); this fills in any missing company
    name or industry from Yahoo Finance and saves the file back."""
    data = json.loads(path.read_text(encoding="utf-8"))
    stocks = data["stocks"]
    todo = [s for s in stocks if not s.get("name") or not s.get("industry")]
    if todo:
        import yfinance as yf
        for s in todo:
            try:
                info = yf.Ticker(s["stock_id"]).info or {}
            except Exception as exc:  # noqa: BLE001
                print(f"[us-universe] {s['stock_id']}: {exc}", file=sys.stderr)
                continue
            name = info.get("shortName") or info.get("longName") or ""
            for tail in (", Inc.", " Inc.", " Inc", " Corporation", " Corp.", " Holdings", " plc", " PLC", " N.V.", " Ltd.", " Co., Ltd."):
                name = name.replace(tail, "")
            s["name"] = s.get("name") or name.strip() or s["stock_id"]
            s["industry"] = s.get("industry") or _yahoo_industry(info.get("sector") or "", info.get("industry") or "")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[us-universe] filled {len(todo)} names/industries from Yahoo", file=sys.stderr)
    for s in stocks:
        s["name"] = s.get("name") or s["stock_id"]
        s["industry"] = s.get("industry") or "其他"
    return stocks


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
