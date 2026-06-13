"""Navigate action — go to event page and pre-load ticket info."""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.core.browser import BrowserManager
from src.anti_detect.humanize import human_delay, human_scroll


class NavigateAction:
    """Navigates to the event detail page and pre-loads ticket information.

    Strategy:
    1. Navigate to event URL from config
    2. Wait for page to fully load
    3. Parse available ticket tiers and button state
    4. Cache DOM references for fast access during buy phase
    """

    def __init__(self, browser: BrowserManager, config: BotConfig):
        self.browser = browser
        self.config = config
        self._page_info: dict = {}

    async def go_to_event_page(self) -> bool:
        """Navigate to the event detail page and wait for it to load.

        First visits the damai homepage to establish a session context,
        then navigates to the event page. Skipping the homepage can cause
        damai to serve a 404 honeypot page.
        """
        page = self.browser.page
        event_url = self.config.event.url

        try:
            # Step 1: Visit homepage to activate the session
            logger.info("Warming up session via homepage...")
            await page.goto("https://www.damai.cn/", wait_until="domcontentloaded")
            await human_delay(500, 1000)

            # Step 2: Navigate to event page
            logger.info(f"Navigating to event page: {event_url}")
            await page.goto(event_url, wait_until="domcontentloaded")
            await human_delay(1000, 2000)
            await human_scroll(page, "down", 300)  # Scroll to ticket section
            logger.info("✅ Event page loaded")
            return True

        except Exception as e:
            logger.error(f"Failed to navigate to event page: {e}")
            return False

    async def parse_ticket_info(self) -> dict:
        """Parse available ticket tiers and button state from the page.

        Returns dict with:
        - tiers: list of available price tiers (text values)
        - button_state: current buy button text
        - button_enabled: whether the buy button is clickable
        """
        page = self.browser.page
        selectors = self.config.selectors.event_page

        info = {
            "tiers": [],
            "button_state": "",
            "button_enabled": False,
        }

        try:
            # Get ticket tier list
            tier_selector = selectors.get(
                "price_tier_list", ".perform__order__select .select_right_list_item"
            )
            tier_elements = await page.query_selector_all(tier_selector)

            for el in tier_elements:
                text = await el.text_content()
                if text:
                    info["tiers"].append(text.strip())

            logger.info(f"Available ticket tiers: {info['tiers']}")

            # Get buy button state
            btn_selector = selectors.get("buy_button", "#buybtn")
            btn_element = await page.query_selector(btn_selector)

            if btn_element:
                btn_text = await btn_element.text_content()
                info["button_state"] = btn_text.strip() if btn_text else ""

                # Check if button is enabled
                is_disabled = await btn_element.get_attribute("disabled")
                info["button_enabled"] = is_disabled is None

                logger.info(
                    f"Buy button state: '{info['button_state']}' "
                    f"(enabled={info['button_enabled']})"
                )

            self._page_info = info
            return info

        except Exception as e:
            logger.warning(f"Failed to parse ticket info: {e}")
            return info

    async def refresh_page(self) -> None:
        """Reload the event page to update button state."""
        page = self.browser.page
        logger.debug("Refreshing event page...")
        try:
            await page.reload(wait_until="domcontentloaded")
            await human_delay(200, 500)
        except Exception as e:
            logger.warning(f"Page refresh failed: {e}")
