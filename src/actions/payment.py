"""Payment detection — detect arrival at payment page and notify user."""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.core.browser import BrowserManager


class PaymentDetector:
    """Detects when the bot reaches the payment page.

    The bot's job ends at the payment page — payment must be completed
    manually by the user. This module:
    1. Detects arrival at payment page by URL or element
    2. Takes a screenshot for the notification
    3. Returns success state so the notifier can alert the user
    """

    # Payment page URL patterns
    PAYMENT_URL_PATTERNS = [
        "**/pay/**",
        "**/payment/**",
        "**/cashier/**",
    ]

    def __init__(self, browser: BrowserManager, config: BotConfig):
        self.browser = browser
        self.config = config

    async def wait_for_payment_page(self, timeout: int = 15000) -> bool:
        """Wait for navigation to the payment page.

        Args:
            timeout: Maximum wait time in milliseconds.

        Returns True if payment page is detected.
        """
        page = self.browser.page
        selectors = self.config.selectors.payment

        logger.info("Waiting for payment page...")

        # Strategy 1: Wait for URL pattern
        for pattern in self.PAYMENT_URL_PATTERNS:
            try:
                await page.wait_for_url(pattern, timeout=timeout)
                logger.info("✅ Payment page detected by URL")
                return True
            except Exception:
                continue

        # Strategy 2: Check for payment page indicator element
        indicator_selector = selectors.get(
            "page_indicator", ".pay-button, #payButton, .payment-confirm"
        )

        # Split the comma-separated selectors
        for sel in indicator_selector.split(","):
            sel = sel.strip()
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    logger.info("✅ Payment page detected by element")
                    return True
            except Exception:
                continue

        # Strategy 3: Check current URL directly
        current_url = page.url
        if any(keyword in current_url for keyword in ["pay", "payment", "cashier"]):
            logger.info("✅ Payment page detected by current URL")
            return True

        logger.warning("Payment page not detected within timeout")
        return False

    async def get_payment_info(self) -> dict:
        """Extract payment page information (QR code, amount, etc.).

        Returns dict with payment details for notification.
        """
        page = self.browser.page
        selectors = self.config.selectors.payment
        info = {"url": page.url}

        # Try to find Alipay QR code image
        qr_selector = selectors.get("alipay_qr", ".alipay-qrcode img")
        try:
            qr_el = await page.query_selector(qr_selector)
            if qr_el:
                qr_src = await qr_el.get_attribute("src")
                info["qr_code_src"] = qr_src
        except Exception:
            pass

        return info
