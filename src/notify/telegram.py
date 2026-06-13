"""Telegram Bot API notifier."""

from __future__ import annotations

import aiohttp
from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """Telegram Bot API notification.

    API docs: https://core.telegram.org/bots/api
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = f"https://api.telegram.org/bot{bot_token}"

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send message via Telegram Bot API."""
        text = f"**{title}**\n\n{body}"

        # Send text message first
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/sendMessage", json=payload
                ) as resp:
                    result = await resp.json()
                    if not result.get("ok"):
                        logger.warning(
                            f"Telegram text message failed: {result}"
                        )

                # Send screenshot as photo if available
                if screenshot_path:
                    import os
                    if os.path.exists(screenshot_path):
                        data = aiohttp.FormData()
                        data.add_field(
                            "chat_id", self.chat_id
                        )
                        data.add_field(
                            "photo",
                            open(screenshot_path, "rb"),
                            filename="screenshot.png",
                            content_type="image/png",
                        )
                        async with session.post(
                            f"{self.api_base}/sendPhoto", data=data
                        ) as resp:
                            result = await resp.json()
                            if not result.get("ok"):
                                logger.warning(
                                    f"Telegram photo send failed: {result}"
                                )

            logger.info("Telegram notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False
