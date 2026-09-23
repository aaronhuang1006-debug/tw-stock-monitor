CREATE TABLE IF NOT EXISTS daily_price (
    stock_id TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_price_stock ON daily_price(stock_id, date);

CREATE TABLE IF NOT EXISTS fetch_log (
    stock_id TEXT NOT NULL,
    run_date TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (stock_id, run_date)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    stock_id TEXT NOT NULL,
    stock_name TEXT,
    signal TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_run_date ON alerts(run_date);
