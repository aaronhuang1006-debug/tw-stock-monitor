import datetime
import time

import requests

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

_FIELD_MAP = {
    "open": "open",
    "max": "high",
    "min": "low",
    "close": "close",
    "Trading_Volume": "volume",
}


def fetch_stock_price(stock_id: str, start_date: str, end_date: str, token: str = "") -> list[dict]:
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(FINMIND_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind error for {stock_id}: {payload.get('msg')}")

    rows = []
    for rec in payload.get("data", []):
        rows.append(
            {
                "date": rec["date"],
                "open": rec.get("open"),
                "high": rec.get("max"),
                "low": rec.get("min"),
                "close": rec.get("close"),
                "volume": rec.get("Trading_Volume"),
            }
        )
    return rows


def fetch_stock_news(stock_id: str, date: str, token: str = "") -> list[dict]:
    # TaiwanStockNews only accepts a single date (no end_date) per FinMind's API.
    params = {"dataset": "TaiwanStockNews", "data_id": stock_id, "start_date": date}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(FINMIND_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind news error for {stock_id}: {payload.get('msg')}")
    return payload.get("data", [])


def fetch_news_for_stocks(stock_ids: list[str], date: str, token: str, requests_per_hour: int,
                           max_per_stock: int = 3, progress_cb=None) -> dict[str, list[dict]]:
    limiter = RateLimiter(requests_per_hour)
    result: dict[str, list[dict]] = {}
    for i, stock_id in enumerate(stock_ids):
        limiter.wait()
        try:
            raw = fetch_stock_news(stock_id, date, token=token)
        except Exception:  # noqa: BLE001
            raw = []

        seen_links = set()
        deduped = []
        for item in sorted(raw, key=lambda r: r.get("date", ""), reverse=True):
            title = item.get("title", "").strip()
            link = item.get("link", "").strip()
            key = link or title
            if not title or not key or key in seen_links:
                continue
            seen_links.add(key)
            deduped.append({"title": title, "link": link, "date": item.get("date", "")})
            if len(deduped) >= max_per_stock:
                break
        result[stock_id] = deduped

        if progress_cb:
            progress_cb(i + 1, len(stock_ids), stock_id)
    return result


def is_trading_day(run_date: str, token: str = "", probe_stock_id: str = "2330") -> bool:
    """Cheap single-request check so a holiday doesn't cost a full universe sweep."""
    rows = fetch_stock_price(probe_stock_id, run_date, run_date, token=token)
    return len(rows) > 0


class RateLimiter:
    def __init__(self, requests_per_hour: int):
        self.min_interval = 3600.0 / max(requests_per_hour, 1)
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()


def fetch_universe(conn, universe: list[dict], run_date: str, token: str, requests_per_hour: int,
                    lookback_days: int, skip_done: bool = True, progress_cb=None) -> dict:
    from . import db

    limiter = RateLimiter(requests_per_hour)
    end_date = run_date
    start_date = (
        datetime.date.fromisoformat(run_date) - datetime.timedelta(days=lookback_days)
    ).isoformat()

    ok, failed, skipped = 0, 0, 0
    for i, stock in enumerate(universe):
        stock_id = stock["stock_id"]
        if skip_done and db.already_fetched(conn, stock_id, run_date):
            skipped += 1
            if progress_cb:
                progress_cb(i + 1, len(universe), stock_id, "skipped")
            continue

        limiter.wait()
        try:
            rows = fetch_stock_price(stock_id, start_date, end_date, token=token)
            if rows:
                db.upsert_prices(conn, stock_id, rows)
            db.log_fetch(conn, stock_id, run_date, datetime.datetime.now().isoformat(timespec="seconds"), "ok")
            ok += 1
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            db.log_fetch(conn, stock_id, run_date, datetime.datetime.now().isoformat(timespec="seconds"), f"error: {exc}")
            failed += 1
            status = f"error: {exc}"

        if progress_cb:
            progress_cb(i + 1, len(universe), stock_id, status)

    return {"ok": ok, "failed": failed, "skipped": skipped, "total": len(universe)}
