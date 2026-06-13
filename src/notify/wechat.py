"""WeChat Work (企业微信) webhook notifier."""

from __future__ import annotations

import aiohttp
from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class WeChatNotifier(BaseNotifier):
    """企业微信 robot webhook notification.

    API docs: https://developer.work.weixin.qq.com/document/path/91770
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send markdown message via WeChat Work webhook."""
        content = f"**{title}**\n\n{body}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

        # If we have a screenshot, send it as an image message
        if screenshot_path:
            # WeChat Work requires uploading image first to get media_id
            # For simplicity, just include the text notification
            pass

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload
                ) as resp:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        logger.info("WeChat notification sent successfully")
                        return True
                    else:
                        logger.warning(
                            f"WeChat notification failed: {result}"
                        )
                        return False
        except Exception as e:
            logger.error(f"WeChat notification error: {e}")
            return False
