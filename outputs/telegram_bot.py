# outputs/telegram_bot.py
import os
import logging
import time
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

def _bot_base_url() -> str:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN nije setovan.")
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> Optional[Dict[str, Any]]:
    url = f"{_bot_base_url()}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    logger.error(f"Telegram error: {data}")
                return data
        except Exception as e:
            last_error = e
            logger.warning(
                "Telegram send attempt %s failed: %s", attempt + 1, e
            )
            time.sleep(2)

    if last_error:
        logger.error("Telegram send failed after retries: %s", last_error)
    return None
