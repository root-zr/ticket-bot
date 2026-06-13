"""Notification base — abstract interface and multi-channel manager."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger


class BaseNotifier(ABC):
    """All notification backends implement this interface."""

    @abstractmethod
    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send a notification. Returns True on success."""
        ...


class NotificationManager:
    """Fans out notifications to all enabled channels.

    Non-blocking: failures in one channel don't block others.
    """

    def __init__(self, channels: list[BaseNotifier]):
        self.channels = channels

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> None:
        """Send notification to all channels concurrently."""
        tasks = [
            self._safe_send(ch, title, body, screenshot_path)
            for ch in self.channels
        ]
        await asyncio.gather(*tasks)

    async def _safe_send(
        self,
        channel: BaseNotifier,
        title: str,
        body: str,
        screenshot_path: Optional[str],
    ) -> None:
        """Send via one channel, catching any errors."""
        try:
            await channel.send(title, body, screenshot_path)
        except Exception as e:
            logger.warning(
                f"Notification failed on {type(channel).__name__}: {e}"
            )
