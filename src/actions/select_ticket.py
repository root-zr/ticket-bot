"""Select ticket action — pick price tier, set quantity, and click buy."""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.core.browser import BrowserManager
from src.anti_detect.humanize import human_click, human_delay, human_fill
from src.anti_detect.captcha import CaptchaHandler


class SelectTicketAction:
    """Selects the target price tier, sets ticket quantity, and clicks buy.

    Strategy:
    1. Click the correct price tier based on config (price_tier or price_text)
    2. Set ticket quantity in the input/dropdown
    3. Click "立即购买" (Buy Now) button
    4. Handle "即将开抢" / "已售罄" button states
    5. Check for captcha after clicking buy
    """

    def __init__(self, browser: BrowserManager, config: BotConfig, captcha_handler: CaptchaHandler):
        self.browser = browser
        self.config = config
        self.captcha_handler = captcha_handler

    async def select_and_buy(self) -> bool:
        """Execute the full ticket selection + buy flow.

        Returns True if successfully clicked buy and navigated to order page.
        """
        page = self.browser.page
        selectors = self.config.selectors.event_page

        # Step 1: Select price tier
        if not await self._select_price_tier():
            return False

        await human_delay(
            self.config.anti_detect.min_action_delay_ms,
            self.config.anti_detect.max_action_delay_ms,
        )

        # Step 2: Set ticket quantity
        if not await self._set_quantity():
            return False

        await human_delay(
            self.config.anti_detect.min_action_delay_ms,
            self.config.anti_detect.max_action_delay_ms,
        )

        # Step 3: Click buy button
        btn_text = selectors.get("buy_button_text_active", "立即购买")
        btn_selector = selectors.get("buy_button", "#buybtn")

        # Check button state first
        btn_element = await page.query_selector(btn_selector)
        if btn_element is None:
            logger.warning("Buy button not found")
            return False

        current_text = (await btn_element.text_content() or "").strip()

        if current_text == selectors.get("buy_button_text_coming_soon", "即将开抢"):
            logger.info("Tickets not yet on sale — need to refresh")
            return False

        if current_text == selectors.get("buy_button_text_sold_out", "已售罄"):
            logger.info("Tickets sold out")
            return False

        if current_text != btn_text:
            logger.warning(f"Unexpected button state: '{current_text}'")
            # Still try to click it
            await human_click(page, btn_selector)

        await human_click(page, btn_selector)

        # Step 4: Check for captcha
        if not await self.captcha_handler.check_and_solve():
            logger.warning("Captcha not solved — cannot proceed")
            return False

        # Step 5: Wait for navigation to order page
        try:
            await page.wait_for_url(
                "**/order/**",
                timeout=5000,
            )
            logger.info("✅ Successfully navigated to order page")
            return True
        except Exception:
            # May still be on event page if buy didn't work
            logger.debug("No navigation to order page detected")
            return await self._check_order_page_arrival()

    async def _select_price_tier(self) -> bool:
        """Select the correct price tier based on config."""
        page = self.browser.page
        selectors = self.config.selectors.event_page

        tier_selector = selectors.get(
            "price_tier_list", ".perform__order__select .select_right_list_item"
        )
        tier_elements = await page.query_selector_all(tier_selector)

        if not tier_elements:
            logger.warning("No price tier elements found on page")
            return False

        # Determine which tier to select
        target_tier = None

        if self.config.event.price_text:
            # Match by exact price text
            for el in tier_elements:
                text = (await el.text_content() or "").strip()
                if self.config.event.price_text in text:
                    target_tier = el
                    logger.info(f"Selected tier by price_text: '{text}'")
                    break
        else:
            # Select by index (price_tier)
            idx = self.config.event.price_tier
            if idx < len(tier_elements):
                target_tier = tier_elements[idx]
                text = (await target_tier.text_content() or "").strip()
                logger.info(f"Selected tier {idx}: '{text}'")

        if target_tier is None:
            logger.warning(
                f"Could not find target tier "
                f"(price_text='{self.config.event.price_text}', "
                f"price_tier={self.config.event.price_tier})"
            )
            return False

        # Click the tier
        await target_tier.click()
        await human_delay(200, 400)
        return True

    async def _set_quantity(self) -> bool:
        """Set the number of tickets to purchase."""
        page = self.browser.page
        selectors = self.config.selectors.event_page

        if self.config.event.ticket_count == 1:
            # Default is usually 1, no need to change
            logger.debug("Ticket count = 1, using default")
            return True

        # Try incrementing via + button
        plus_selector = selectors.get("quantity_plus_btn", ".cafeine-num-plus")
        input_selector = selectors.get("quantity_input", ".cafeine-num-input")

        # Try setting value via input first
        input_el = await page.query_selector(input_selector)
        if input_el:
            current_val = await input_el.input_value()
            if int(current_val) != self.config.event.ticket_count:
                await human_fill(page, input_selector, str(self.config.event.ticket_count))
                logger.info(f"Set ticket count to: {self.config.event.ticket_count}")
            return True

        # Fallback: click + button multiple times
        plus_el = await page.query_selector(plus_selector)
        if plus_el:
            for _ in range(self.config.event.ticket_count - 1):
                await human_click(page, plus_selector, 100, 300)
            logger.info(f"Set ticket count via + button to: {self.config.event.ticket_count}")
            return True

        logger.warning("Could not set ticket quantity")
        return False

    async def _check_order_page_arrival(self) -> bool:
        """Check if we've arrived at the order confirmation page."""
        page = self.browser.page
        current_url = page.url

        if "order" in current_url or "confirm" in current_url:
            logger.info("✅ Arrived at order page")
            return True

        return False
