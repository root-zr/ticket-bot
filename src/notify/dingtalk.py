"""DingTalk (钉钉) robot webhook notifier."""

from __future__ import annotations

import hashlib
import hmac
import time
import base64
import aiohttp
from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class DingTalkNotifier(BaseNotifier):
    """钉钉 custom robot webhook notification.

    API docs: https://open.dingtalk.com/document/orgapp/custom-robots-send-group-messages
    Supports signed webhook (with secret) for security.
    """

    def __init__(self, webhook_url: str, secret: str = ""):
        self.webhook_url = webhook_url
        self.secret = secret

    def _sign_url(self) -> str:
        """Generate signed webhook URL with timestamp and sign."""
        if not self.secret:
            return self.webhook_url

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send markdown message via DingTalk webhook."""
        url = self._sign_url()

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{body}",
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        logger.info("DingTalk notification sent successfully")
                        return True
                    else:
                        logger.warning(
                            f"DingTalk notification failed: {result}"
                        )
                        return False
        except Exception as e:
            logger.error(f"DingTalk notification error: {e}")
            return False
