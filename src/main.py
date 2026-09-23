import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db, fetch_data, indicators, screener, report, notify_telegram, notify_email  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))

    # Secrets never live in the committed config file — in CI (GitHub Actions)
    # they come from repo Secrets as env vars; locally settings.yaml (gitignored)
    # can just hold real values directly and these overrides are no-ops.
    if os.environ.get("FINMIND_TOKEN"):
        cfg["finmind"]["token"] = os.environ["FINMIND_TOKEN"]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        cfg["notify"]["telegram"]["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        cfg["notify"]["telegram"]["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
    if os.environ.get("EMAIL_TO"):
        cfg["notify"]["email"]["to"] = os.environ["EMAIL_TO"]
    return cfg


def load_universe(path: str) -> list[dict]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return data["stocks"]


def main() -> None:
    parser = argparse.ArgumentParser(description="台股K線技術指標監測系統")
    parser.add_argument("--limit", type=int, default=None, help="僅處理前N檔股票(測試用)")
    parser.add_argument("--skip-fetch", action="store_true", help="略過抓取,直接用DB既有資料計算(測試用)")
    parser.add_argument("--date", type=str, default=None, help="指定抓取的目標日期(預設今天),格式YYYY-MM-DD")
    args = parser.parse_args()

    cfg = load_settings()
    universe = load_universe(cfg["universe_file"])
    if args.limit:
        universe = universe[: args.limit]

    conn = db.connect(str(ROOT / cfg["db_path"]))
    run_date = args.date or datetime.date.today().isoformat()

    fetch_stats = {"ok": 0, "failed": 0, "skipped": len(universe), "total": len(universe)}
    if not args.skip_fetch:
        if not fetch_data.is_trading_day(run_date, token=cfg["finmind"]["token"]):
            print(f"[skip] {run_date} 無交易資料(非交易日),不產生報表也不發送通知。")
            return

        def progress(i, total, stock_id, status):
            if i % 20 == 0 or i == total:
                print(f"[fetch] {i}/{total} {stock_id} {status}", file=sys.stderr)

        fetch_stats = fetch_data.fetch_universe(
            conn,
            universe,
            run_date,
            token=cfg["finmind"]["token"],
            requests_per_hour=cfg["finmind"]["requests_per_hour"],
            lookback_days=cfg["finmind"]["lookback_days"],
            progress_cb=progress,
        )
        print(f"[fetch] done: {fetch_stats}", file=sys.stderr)

    # A non-trading day (weekend or holiday) has no bar for run_date even
    # though the weekday cron still fires; skip everything past this point
    # rather than re-notifying on stale data from the last trading day.
    cur = conn.execute("SELECT COUNT(*) FROM daily_price WHERE date=?", (run_date,))
    has_data_today = cur.fetchone()[0] > 0
    if not has_data_today:
        print(f"[skip] {run_date} 無交易資料(非交易日),不產生報表也不發送通知。")
        return
    effective_date = run_date

    ind_cfg = cfg["indicators"]
    all_alerts = []
    all_snapshots = []
    name_map = {s["stock_id"]: s["name"] for s in universe}

    for stock in universe:
        stock_id = stock["stock_id"]
        df = db.load_price_history(conn, stock_id, min_rows=ind_cfg["new_high_low_period"])
        if df is None:
            continue
        df = indicators.compute_all(df, ind_cfg)
        if df.iloc[-1]["date"] != effective_date:
            continue

        snapshot = indicators.latest_snapshot(df)
        snapshot.update({"stock_id": stock_id, "name": name_map.get(stock_id, "")})
        all_snapshots.append(snapshot)

        signals = screener.screen_stock(df, ind_cfg)
        for s in signals:
            all_alerts.append(
                {
                    "stock_id": stock_id,
                    "stock_name": name_map.get(stock_id, ""),
                    "signal": s["signal"],
                    "detail": s["detail"],
                }
            )

    news_map = {}
    news_cfg = cfg.get("news", {})
    if news_cfg.get("enabled") and all_alerts:
        triggered_ids = sorted({a["stock_id"] for a in all_alerts})

        def news_progress(i, total, stock_id):
            if i % 10 == 0 or i == total:
                print(f"[news] {i}/{total} {stock_id}", file=sys.stderr)

        news_map = fetch_data.fetch_news_for_stocks(
            triggered_ids,
            effective_date,
            token=cfg["finmind"]["token"],
            requests_per_hour=cfg["finmind"]["requests_per_hour"],
            max_per_stock=news_cfg.get("max_per_stock", 3),
            progress_cb=news_progress,
        )
        print(f"[news] done: {len(triggered_ids)} 檔已查詢", file=sys.stderr)

    db.save_alerts(conn, effective_date, all_alerts)
    csv_path = report.write_csv_report(str(ROOT / cfg["report_dir"]), effective_date, all_alerts)
    html_path = report.write_html_report(str(ROOT / cfg["report_dir"]), effective_date, all_alerts, universe, news_map, all_snapshots)
    artifact_path = report.write_artifact_source(str(ROOT / cfg["report_dir"]), effective_date, all_alerts, universe, news_map, all_snapshots)
    summary = report.build_summary_text(effective_date, all_alerts, fetch_stats, universe)

    # Stable path for GitHub Pages (docs/ on main) — overwritten every run,
    # independent of the dated reports/ files above.
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(Path(artifact_path).read_text(encoding="utf-8"), encoding="utf-8")

    print(summary)
    print(f"\n[report] CSV: {csv_path}")
    print(f"[report] HTML: {html_path}")
    print(f"[report] Pages: {docs_dir / 'index.html'}")
    artifact_url = cfg.get("artifact", {}).get("url", "")
    if artifact_url:
        print(f"[artifact] ARTIFACT_PENDING source={artifact_path} url={artifact_url}")

    tg_cfg = cfg["notify"]["telegram"]
    if tg_cfg.get("enabled") and tg_cfg.get("bot_token") and tg_cfg.get("chat_id"):
        notify_telegram.send_telegram(tg_cfg["bot_token"], tg_cfg["chat_id"], summary)
        print("[notify] telegram sent", file=sys.stderr)

    email_cfg = cfg["notify"]["email"]
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if email_cfg.get("enabled") and email_cfg.get("to") and gmail_address and gmail_app_password:
        subject = f"台股監測報表 {effective_date}"
        body = summary + f"\n\n完整視覺化報表請見: {cfg.get('pages_url', '')}".rstrip()
        notify_email.send_email(gmail_address, gmail_app_password, email_cfg["to"], subject, body)
        print("[notify] email sent via smtp", file=sys.stderr)
    elif email_cfg.get("enabled") and email_cfg.get("to"):
        # No SMTP credentials in this environment (e.g. a manual local run without
        # GMAIL_APP_PASSWORD set) — leave a marker instead of failing outright.
        print(f"[notify] EMAIL_PENDING to={email_cfg['to']} subject=台股監測報表 {effective_date}")


if __name__ == "__main__":
    main()
