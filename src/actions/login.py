"""Login action — cookie restoration or QR code login."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import Page, BrowserContext

from src.config.loader import BotConfig
from src.core.browser import BrowserManager
from src.persistence.cookies import CookieStore
from src.anti_detect.humanize import human_delay


class LoginAction:
    """Handles login to damai.cn via cookie restoration or QR code scanning.

    Strategy:
    1. Try restoring saved cookies → check if session is still valid
    2. If expired or no cookies: navigate to login page, show QR code
    3. Wait for user to scan QR code with 大麦 app
    4. Save new cookies for future runs
    """

    # URLs
    LOGIN_URL = "https://passport.damai.cn/login"
    HOME_URL = "https://www.damai.cn/"
    LOGIN_SUCCESS_URL_PATTERN = "**/user/**"

    def __init__(self, browser: BrowserManager, config: BotConfig):
        self.browser = browser
        self.config = config
        self.cookie_store = CookieStore(config.persistence.cookies_file)

    async def restore_or_login(self) -> bool:
        """Attempt cookie restoration, fall back to interactive login.

        Returns True if login is successful.
        """
        # Step 1: Try cookie restoration
        if self.cookie_store.exists() and not self.cookie_store.is_expired():
            logger.info("Attempting to restore saved cookies...")
            # Cookies are already loaded via BrowserManager.start() storage_state
            # Verify by checking if we're logged in
            if await self._verify_session():
                logger.info("✅ Session restored from saved cookies")
                return True
            else:
                logger.warning("Saved cookies are invalid — need to re-login")

        # Step 2: Interactive login
        return await self._interactive_login()

    async def _verify_session(self) -> bool:
        """Check if the current session is valid by visiting homepage."""
        page = self.browser.page
        try:
            await page.goto(self.HOME_URL, wait_until="domcontentloaded")
            await human_delay(500, 1000)

            # Check for login indicator (username displayed in header)
            selectors = self.config.selectors.login
            indicator = selectors.get("login_success_indicator", ".header-user-name")

            element = await page.query_selector(indicator)
            if element and await element.is_visible():
                return True

            # Alternative: check if login button is NOT visible
            login_btn = await page.query_selector(".header-login-btn, .login-btn")
            if login_btn is None:
                return True

            return False

        except Exception as e:
            logger.warning(f"Session verification failed: {e}")
            return False

    async def _interactive_login(self) -> bool:
        """Navigate to login page and wait for user to scan QR code."""
        page = self.browser.page
        logger.info("Navigating to login page...")

        try:
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            await human_delay(500, 1000)

            logger.info(
                "请在浏览器中扫描二维码登录... "
                "(Scan QR code with 大麦 app — if headless, switch to headful mode)"
            )

            # Wait for login success (URL redirect or element appearance)
            try:
                await page.wait_for_url(
                    self.LOGIN_SUCCESS_URL_PATTERN,
                    timeout=120_000,  # 2 minutes to scan
                )
                logger.info("✅ Login successful!")
            except Exception:
                # Alternative: wait for username element to appear
                selectors = self.config.selectors.login
                indicator = selectors.get("login_success_indicator", ".header-user-name")
                try:
                    await page.wait_for_selector(
                        indicator, state="visible", timeout=120_000
                    )
                    logger.info("✅ Login successful!")
                except Exception as e:
                    logger.error(f"Login timed out: {e}")
                    return False

            # Save cookies after successful login
            await self.browser.save_storage_state()
            return True

        except Exception as e:
            logger.error(f"Interactive login failed: {e}")
            return False
