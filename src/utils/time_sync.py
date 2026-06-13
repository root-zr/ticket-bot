"""NTP time synchronization — provides clock-corrected time for precision timing."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import ntplib
from loguru import logger


class NTPClock:
    """Provides NTP-corrected time. Falls back to system time if NTP fails.

    Millisecond-level time sync is critical for ticket-snatching —
    system clocks can drift seconds, which means the bot may start too
    early or too late.
    """

    def __init__(self, server: str = "ntp.aliyun.com"):
        self.server = server
        self.offset: float = 0.0  # seconds ahead of system clock
        self._sync()

    def _sync(self) -> None:
        """Query NTP server and compute clock offset."""
        try:
            client = ntplib.NTPClient()
            response = client.request(self.server, version=3, timeout=5)
            self.offset = response.offset
            logger.info(
                f"NTP sync complete — offset: {self.offset:+.4f}s from {self.server}"
            )
        except Exception as e:
            logger.warning(f"NTP sync failed, using system time: {e}")
            self.offset = 0.0

    def now(self) -> datetime:
        """Return current UTC time corrected by NTP offset."""
        system_now = time.time()
        corrected = system_now + self.offset
        return datetime.fromtimestamp(corrected, tz=timezone.utc)

    def now_cst(self) -> datetime:
        """Return current China Standard Time (UTC+8)."""
        cst = timezone(timedelta(hours=8))
        return self.now().astimezone(cst)

    def seconds_until(self, target_iso: str) -> float:
        """Seconds from now until target time (ISO format with timezone).

        Args:
            target_iso: ISO 8601 datetime string, e.g. "2026-06-15T10:00:00+08:00".
        """
        target = datetime.fromisoformat(target_iso)
        if target.tzinfo is None:
            # Assume CST if no timezone specified
            target = target.replace(tzinfo=timezone(timedelta(hours=8)))
        delta = target - self.now()
        return delta.total_seconds()
