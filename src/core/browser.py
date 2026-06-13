"""Browser lifecycle manager — Playwright Chromium with stealth patches."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from src.config.loader import BrowserConfig, BotConfig
from src.anti_detect.fingerprint import apply_stealth


class BrowserManager:
    """Manages Playwright browser instance lifecycle.

    - Launches Chromium with anti-detection patches
    - Provides page factory with stealth context
    - Handles cookie restoration via storage state
    - Supports headless/headful toggle for debugging
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.browser_config = config.browser
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def page(self) -> Page:
        """Get the current active page."""
        if self._page is None:
            raise RuntimeError("Browser not started — call start() first")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get the current browser context."""
        if self._context is None:
            raise RuntimeError("Browser not started — call start() first")
        return self._context

    async def start(self) -> Page:
        """Launch browser, create stealth context, and return a new page."""
        logger.info(
            f"Starting browser — headless={self.browser_config.headless}"
        )

        self._playwright = await async_playwright().start()

        # Launch Chromium
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
        if self.browser_config.proxy:
            launch_args.append(f"--proxy-server={self.browser_config.proxy}")

        self._browser = await self._playwright.chromium.launch(
            headless=self.browser_config.headless,
            slow_mo=self.browser_config.slow_mo,
            args=launch_args,
        )

        # Create context with stealth settings
        context_kwargs = {
            "viewport": {
                "width": self.browser_config.viewport.width,
                "height": self.browser_config.viewport.height,
            },
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }
        if self.browser_config.user_agent:
            context_kwargs["user_agent"] = self.browser_config.user_agent

        # Try to restore cookies from saved storage state
        cookies_path = Path(self.config.persistence.cookies_file)
        if cookies_path.exists():
            logger.info(f"Restoring cookies from: {cookies_path}")
            context_kwargs["storage_state"] = str(cookies_path)

        self._context = await self._browser.new_context(**context_kwargs)

        # Apply stealth patches
        if self.config.anti_detect.stealth_mode:
            await apply_stealth(self._context)

        # Set default timeout
        self._context.set_default_timeout(self.browser_config.timeout)

        # Create main page
        self._page = await self._context.new_page()

        logger.info("Browser started successfully")
        return self._page

    async def save_storage_state(self) -> str:
        """Save current browser context storage state (cookies + localStorage)."""
        cookies_path = Path(self.config.persistence.cookies_file)
        cookies_path.parent.mkdir(parents=True, exist_ok=True)

        state = await self._context.storage_state(path=str(cookies_path))
        logger.info(f"Storage state saved to: {cookies_path}")
        return str(cookies_path)

    async def close(self) -> None:
        """Close browser and playwright gracefully."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")
