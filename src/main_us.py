"""US signal board: Nasdaq-100 + PHLX Semiconductor, same indicators and page as the Taiwan board.

Writes docs/us/index.html (+ history, tracking). No Telegram. Run: python -m src.main_us
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import breadth, db, history, indicators, report, screener, tracking, us_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "us"


def already_published(run_date: str) -> bool:
    page = OUT / "index.html"
    return page.exists() and f'<span class="date">{run_date}(' in page.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="美股訊號板")
    ap.add_argument("--force", action="store_true", help="re-run even if the latest day is already published")
    ap.add_argument("--db", default="data/us.db")
    args = ap.parse_args()

    cfg_path = ROOT / "config" / ("settings.yaml" if (ROOT / "config" / "settings.yaml").exists() else "settings.ci.yaml")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    ind_cfg = cfg["indicators"]

    universe = us_data.refresh_universe(ROOT / "config" / "universe_us.json")
    if not universe:
        print("[us] no universe; stopping", file=sys.stderr)
        sys.exit(1)
    conn = db.connect(str(ROOT / args.db))
    # Adjusted prices shift whenever a dividend goes ex, so always reload the whole lookback window.
    start = (datetime.date.today() - datetime.timedelta(days=cfg.get("lookback_days", 460) + 60)).isoformat()
    stats = us_data.download(conn, [s["stock_id"] for s in universe], start)
    print(f"[us] prices: {stats['ok']} ok, missing {stats['missing']}", file=sys.stderr)

    # The latest date most tickers have is the trading day to report.
    row = conn.execute("""SELECT date, COUNT(*) c FROM daily_price GROUP BY date ORDER BY date DESC LIMIT 5""").fetchall()
    effective_date = next((d for d, c in row if c >= 0.8 * stats["ok"]), None)
    if not effective_date:
        print("[us] no complete trading day found", file=sys.stderr)
        return
    if already_published(effective_date) and not args.force:
        print(f"[skip] {effective_date} 已發布過", file=sys.stderr)
        return

    alerts, snapshots, tails = [], [], {}
    for s in universe:
        sid = s["stock_id"]
        df = db.load_price_history(conn, sid, min_rows=ind_cfg["new_high_low_period"])
        if df is None:
            continue
        df = indicators.compute_all(df, ind_cfg)
        if df.iloc[-1]["date"] != effective_date:
            continue
        tails[sid] = df[["date", "close", "ma20"]].tail(60)
        weekly = indicators.weekly_table(df, ind_cfg)
        snap = indicators.latest_snapshot(df)
        snap.update(indicators.weekly_snapshot(weekly, ind_cfg))
        snap.update({"stock_id": sid, "name": s["name"]})
        snapshots.append(snap)
        for sig in (screener.screen_stock(df, ind_cfg) + screener.screen_weekly(df, weekly, ind_cfg)
                    + screener.screen_weekly_provisional(df, weekly, ind_cfg)):
            alerts.append({"stock_id": sid, "stock_name": s["name"], "signal": sig["signal"], "detail": sig["detail"]})

    OUT.mkdir(parents=True, exist_ok=True)
    hist_path = OUT / "history.json"
    hist = history.load(hist_path)
    added = history.replay_missing(conn, universe, ind_cfg, hist, exclude={effective_date},
                                   max_days=cfg.get("history_days", 120), min_rows=ind_cfg["new_high_low_period"])
    history.put_day_from_alerts(hist, effective_date, len(snapshots), alerts)
    history.trim(hist, cfg.get("history_days", 120))
    history.save(hist_path, hist)

    track = None
    try:
        log_path = OUT / "track_log.json"
        log = tracking.load_log(log_path, seed=hist)
        tracking.record_day(log, effective_date, len(snapshots), alerts)
        tracking.save_log(log_path, log)
        track = tracking.compute(conn, log, [s["stock_id"] for s in universe], ROOT / "backtest" / "results_us" / "results.json")
        (OUT / "tracking.json").write_text(json.dumps(track, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[us-tracking] skipped: {exc}", file=sys.stderr)

    breadth_data = None
    try:
        bench = us_data.benchmark("QQQ", start)
        breadth_data = breadth.compute(conn, [s["stock_id"] for s in universe], effective_date, bench, "QQQ")
    except Exception as exc:  # noqa: BLE001
        print(f"[us-breadth] skipped: {exc}", file=sys.stderr)

    page = report.build_artifact_html(effective_date, alerts, universe, None, snapshots, hist,
                                      history.build_series(tails), track, market=report.MARKET_US,
                                      breadth=breadth_data)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"[us] {effective_date}: {len(snapshots)} 檔, {len(alerts)} 個訊號, 回補 {added} 天", file=sys.stderr)


if __name__ == "__main__":
    main()
