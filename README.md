# 台股技術指標監測系統

每日收盤後自動抓取台灣50(0050)+中型100(0051)成分股+台股規模前20大股票型ETF(共170檔)的K線資料,計算常見技術指標,篩出當日觸發訊號的股票,並可推播到 Telegram / Email。

## 監測範圍與指標

- **股票池**:`config/universe.json`,共170檔
  - 150檔:台灣50+中型100成分股(每季3/6/9/12月換股,建議手動更新這部分)
  - 20檔:台股規模前20大股票型ETF(0050、0056、00878等,不含債券型與國際市場ETF,建議每年檢視一次規模排名),產業別統一標為「ETF」
- **指標**(任一觸發即列入,ETF與個股適用同一套邏輯):
  - 均線黃金交叉/死亡交叉(MA5 vs MA20)
  - RSI 超買(>70)/超賣(<30)
  - MACD 金叉/死叉
  - 布林通道突破上軌/跌破下軌
  - 成交量異常放大(>5日均量2倍)
  - 創60日新高/新低

全部參數可在 `config/settings.yaml` 調整。

## 相關新聞佐證

對於當天有觸發訊號的股票(不是全部170檔),額外查詢 FinMind 的 `TaiwanStockNews` 資料集,去重後列出最新幾則新聞標題與連結,顯示在HTML報表與Artifact每檔股票底下,方便判斷訊號是否有基本面/消息面的原因。純資料抓取與去重,不做AI摘要判讀。

設定在 `config/settings.yaml`:
```yaml
news:
  enabled: true
  max_per_stock: 3
```

注意:新聞品質參差(多為 CMoney 論壇轉貼,非第一手財經媒體),僅供參考線索,不是嚴謹的新聞來源。

## 個股搜尋

HTML報表與Artifact網頁都有搜尋框,可輸入代號或名稱查詢**170檔監測池裡任一檔**目前的指標數值(收盤價、MA5/20/60、RSI、MACD、布林通道、量比),不限於當天有觸發訊號的股票——沒觸發訊號的股票一樣查得到數值,只是不會有彩色標籤。僅限監測池內的170檔,不含其他台股。

## 資料來源

[FinMind API](https://finmind.github.io/) — 免費方案 300次/小時(匿名)或 600次/小時(註冊會員)。
到 https://finmindtrade.com 免費註冊後,把 token 填進 `config/settings.yaml` 的 `finmind.token`,並把 `requests_per_hour` 調到 550 左右,抓取速度會快一倍。

170檔在免費方案下,單次全量抓取約需 20~35 分鐘(視 token 而定)。

## 安裝

```bash
cd ~/stock-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 手動執行

```bash
source .venv/bin/activate
python -m src.main                 # 完整跑一次(抓資料+計算+篩選+產報表)
python -m src.main --limit 5       # 只跑前5檔,測試用
python -m src.main --skip-fetch    # 略過抓資料,只用DB既有資料重算(測試指標邏輯用)
```

執行完會在終端機印出當日觸發清單摘要,並在 `reports/YYYY-MM-DD.csv` 與 `.html` 產出完整報表。

## 通知設定

編輯 `config/settings.yaml`:

```yaml
notify:
  telegram:
    enabled: true
    bot_token: "你的Bot Token"
    chat_id: "你的chat id"
  email:
    enabled: true
    to: "你的信箱"
```

**Telegram Bot 申請步驟**:
1. Telegram 搜尋 `@BotFather`,傳送 `/newbot`,依指示取得 Bot Token
2. 跟你的新 Bot 傳一則訊息(隨便說話),然後瀏覽器打開
   `https://api.telegram.org/bot<你的TOKEN>/getUpdates`,在回傳的 JSON 裡找到
   `"chat":{"id": ...}`,那個數字就是 chat_id

**Email(本機手動執行時)**:若設定了 `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` 環境變數,會直接用SMTP寄送;沒設定的話會印出 `EMAIL_PENDING` 標記行,不會失敗。

## 非交易日自動略過

排程雖然平日都會觸發,但若當天是國定假日等非交易日(FinMind當天查無資料),程式會自動偵測並直接跳過,不產生報表、不發送任何通知。

## 雲端排程(GitHub Actions)

本系統改用 **GitHub Actions** 排程,完全不依賴本機電腦開機或任何App保持開啟,是真正24小時獨立運作的雲端排程。

- 排程設定在 `.github/workflows/daily.yml`,平日 UTC 10:00(台灣時間18:00)自動觸發,也可以在GitHub網頁的Actions分頁手動點「Run workflow」立即執行
- 執行環境用 `config/settings.ci.yaml` 當設定範本(不含任何機密值),所有機密改由 **GitHub Secrets** 提供,執行時由 `src/main.py` 從環境變數覆寫,機密內容不會出現在版控裡
- 抓到的歷史K線資料庫(`data/stock.db`)透過 GitHub Actions 的 cache 機制在每次執行間保留,不需要每次重新回補
- 視覺化報表寫到 `docs/index.html`,交由 **GitHub Pages** 托管(repo設定為 Pages 從 `main` 分支的 `/docs` 資料夾發布),每次執行後自動 commit + push 更新同一個網址

**需要在 GitHub repo 的 Settings → Secrets and variables → Actions 設定這些 Secrets**:

| Secret 名稱 | 說明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Telegram chat id |
| `EMAIL_TO` | 收件信箱 |
| `GMAIL_ADDRESS` | 寄件用的 Gmail 帳號 |
| `GMAIL_APP_PASSWORD` | Gmail「應用程式密碼」(不是登入密碼本身,到 Google帳號→安全性→兩步驟驗證→應用程式密碼 產生) |
| `FINMIND_TOKEN`(選填) | FinMind 註冊token,有填的話可以把 `config/settings.ci.yaml` 裡的 `requests_per_hour` 調到550加快執行速度 |

## 資料庫

`data/stock.db`(SQLite),儲存每檔股票的歷史日K線,供指標滾動計算使用。首次執行會回補約100個交易日的歷史資料。GitHub Actions環境下靠actions/cache在每次執行間保留這個檔案。

## 已知限制

- 免費 FinMind 方案無法一次抓全市場,採逐檔請求,已用內建 RateLimiter 控制頻率避免超過額度
- ETF成分股清單為手動維護快照(2026-09-16擷取),每季需視元大投信官網更新
- GitHub Pages網址預設是公開的,任何拿到連結的人都看得到報表內容
