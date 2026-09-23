import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def upsert_prices(conn: sqlite3.Connection, stock_id: str, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO daily_price (stock_id, date, open, high, low, close, volume)
        VALUES (:stock_id, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT(stock_id, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume
        """,
        [{**r, "stock_id": stock_id} for r in rows],
    )
    conn.commit()


def log_fetch(conn: sqlite3.Connection, stock_id: str, run_date: str, fetched_at: str, status: str) -> None:
    conn.execute(
        """
        INSERT INTO fetch_log (stock_id, run_date, fetched_at, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(stock_id, run_date) DO UPDATE SET fetched_at=excluded.fetched_at, status=excluded.status
        """,
        (stock_id, run_date, fetched_at, status),
    )
    conn.commit()


def already_fetched(conn: sqlite3.Connection, stock_id: str, run_date: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM fetch_log WHERE stock_id=? AND run_date=? AND status='ok'",
        (stock_id, run_date),
    )
    return cur.fetchone() is not None


def load_price_history(conn: sqlite3.Connection, stock_id: str, min_rows: int = 1):
    import pandas as pd

    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM daily_price WHERE stock_id=? ORDER BY date",
        conn,
        params=(stock_id,),
    )
    if len(df) < min_rows:
        return None
    return df


def save_alerts(conn: sqlite3.Connection, run_date: str, alerts: list[dict]) -> None:
    import datetime

    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM alerts WHERE run_date=?", (run_date,))
    conn.executemany(
        """
        INSERT INTO alerts (run_date, stock_id, stock_name, signal, detail, created_at)
        VALUES (:run_date, :stock_id, :stock_name, :signal, :detail, :created_at)
        """,
        [{**a, "run_date": run_date, "created_at": now} for a in alerts],
    )
    conn.commit()
