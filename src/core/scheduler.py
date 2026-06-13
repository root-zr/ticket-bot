"""Countdown scheduler — NTP-synced countdown and timed page refresh."""

from __future__ import annotations

import asyncio
from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.utils.time_sync import NTPClock


class CountdownScheduler:
    """NTP-synced countdown timer with pre-load and refresh phases.

    Timeline:
    T-30s: Pre-load phase — navigate to event page
    T-5s:  Tight countdown — rapid page refreshes
    T+0:   Sale time — trigger buy action
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.ntp_clock = NTPClock(config.timing.ntp_server)
        self._sale_time_iso = config.timing.sale_time

    async def wait_until_sale_time(
        self,
        page: Page,
        refresh_interval_ms: int = 500,
    ) -> None:
        """Wait until sale time with countdown phases.

        Phase 1: Coarse countdown (>5s before sale)
            - Sleep in larger intervals (1s)
        Phase 2: Fine countdown (<5s before sale)
            - Rapid page refreshes every refresh_interval_ms
        Phase 3: Go signal
            - Exact sale time reached, return to trigger buy

        Args:
            page: Playwright page for refresh operations.
            refresh_interval_ms: Page refresh interval in final countdown phase.
        """
        remaining = self.ntp_clock.seconds_until(self._sale_time_iso)
        pre_load_seconds = self.config.timing.pre_load_seconds

        if remaining <= 0:
            logger.warning("Sale time is already past — proceeding immediately")
            return

        logger.info(
            f"Countdown started — {remaining:.1f}s until sale time "
            f"(NTP offset: {self.ntp_clock.offset:+.4f}s)"
        )

        # Phase 1: Coarse countdown (>5s before)
        while remaining > 5:
            sleep_time = min(1.0, remaining - 5)
            logger.debug(f"Countdown: {remaining:.1f}s remaining")
            await asyncio.sleep(sleep_time)
            remaining = self.ntp_clock.seconds_until(self._sale_time_iso)

        # Phase 2: Fine countdown (<5s) — rapid refreshes
        logger.info("⚡ Entering final countdown phase — rapid refreshes")
        while remaining > 0.5:
            # Refresh page to update button state
            try:
                await page.reload(wait_until="domcontentloaded")
            except Exception as e:
                logger.debug(f"Refresh failed: {e}")

            await asyncio.sleep(refresh_interval_ms / 1000)
            remaining = self.ntp_clock.seconds_until(self._sale_time_iso)

        # Phase 3: Final sub-second wait
        logger.info("🔥 Sale time imminent — final wait")
        while remaining > 0:
            await asyncio.sleep(0.01)
            remaining = self.ntp_clock.seconds_until(self._sale_time_iso)

        logger.info("🚀 SALE TIME — GO!")
