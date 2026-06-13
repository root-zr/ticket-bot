"""Bark push notification for iOS."""

from __future__ import annotations

import aiohttp
from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class BarkNotifier(BaseNotifier):
    """Bark push notification for iOS.

    https://github.com/Finb/Bark
    Simple URL-based push: https://api.day.app/{device_key}/{title}/{body}
    """

    def __init__(self, server: str = "https://api.day.app", device_key: str = ""):
        self.server = server.rstrip("/")
        self.device_key = device_key

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send push notification via Bark."""
        if not self.device_key:
            logger.warning("Bark device_key not configured — skipping")
            return False

        url = f"{self.server}/{self.device_key}/{title}/{body}"
        params = {
            "sound": "alarm",
            "group": "DamaiBot",
            "level": "timeSensitive",  # iOS 15+ critical notification
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    result = await resp.json()
                    if result.get("code") == 200:
                        logger.info("Bark notification sent successfully")
                        return True
                    else:
                        logger.warning(f"Bark notification failed: {result}")
                        return False
        except Exception as e:
            logger.error(f"Bark notification error: {e}")
            return False
