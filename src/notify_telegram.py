import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

MAX_LEN = 3500  # leave headroom under Telegram's 4096 char limit


def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API.format(token=bot_token)
    for chunk in _split(text, MAX_LEN):
        resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=15)
        resp.raise_for_status()


def _split(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks, current = [], []
    length = 0
    for line in text.split("\n"):
        if length + len(line) + 1 > max_len:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks
