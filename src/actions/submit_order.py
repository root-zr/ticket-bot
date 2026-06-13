"""Submit order action — fill viewer info and submit order on confirmation page."""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.core.browser import BrowserManager
from src.anti_detect.humanize import human_click, human_delay
from src.anti_detect.captcha import CaptchaHandler


class SubmitOrderAction:
    """Fills order confirmation page and submits the order.

    On the order confirmation page:
    1. Select viewer(s) from saved viewer list
    2. Check agreement checkboxes
    3. Click "提交订单" (Submit Order)
    4. Handle "人数过多" (too many people) queue errors
    5. Check for captcha after submission
    """

    def __init__(self, browser: BrowserManager, config: BotConfig, captcha_handler: CaptchaHandler):
        self.browser = browser
        self.config = config
        self.captcha_handler = captcha_handler

    async def fill_and_submit(self) -> bool:
        """Fill order form and submit.

        Returns True if order was submitted successfully.
        """
        page = self.browser.page
        selectors = self.config.selectors.order_page

        logger.info("Filling order confirmation page...")

        # Step 1: Select viewers
        if not await self._select_viewers():
            logger.warning("Could not select viewers — attempting to continue anyway")

        await human_delay(
            self.config.anti_detect.min_action_delay_ms,
            self.config.anti_detect.max_action_delay_ms,
        )

        # Step 2: Check agreement checkbox
        if not await self._check_agreement():
            logger.warning("Could not check agreement checkbox")

        await human_delay(
            self.config.anti_detect.min_action_delay_ms,
            self.config.anti_detect.max_action_delay_ms,
        )

        # Step 3: Click submit button
        submit_selector = selectors.get(
            "submit_button", 'button:text("提交订单")'
        )
        submit_alt_selector = selectors.get(
            "submit_button_alt", ".submit-wrapper .submit-btn"
        )

        try:
            submit_el = await page.query_selector(submit_selector)
            if submit_el is None:
                submit_el = await page.query_selector(submit_alt_selector)

            if submit_el is None:
                logger.error("Submit button not found on order page")
                return False

            await human_click(page, submit_selector)

        except Exception as e:
            logger.warning(f"Submit button click failed: {e}")
            # Try alternative selector
            try:
                await human_click(page, submit_alt_selector)
            except Exception as e2:
                logger.error(f"Alternative submit button also failed: {e2}")
                return False

        # Step 4: Check for captcha
        await human_delay(500, 1000)
        if not await self.captcha_handler.check_and_solve():
            logger.warning("Captcha detected on order page — not solved")
            return False

        # Step 5: Check for queue error "人数过多"
        try:
            error_el = await page.query_selector(
                '.error-msg, .queue-tip, [class*="人数过多"]'
            )
            if error_el and await error_el.is_visible():
                error_text = await error_el.text_content()
                logger.warning(f"Queue error: {error_text}")
                return False
        except Exception:
            pass

        logger.info("✅ Order submitted")
        return True

    async def _select_viewers(self) -> bool:
        """Select viewer(s) from the saved viewer list."""
        page = self.browser.page
        selectors = self.config.selectors.order_page

        checkbox_selector = selectors.get(
            "viewer_checkbox", ".buyer-list-item input[type='checkbox']"
        )

        try:
            checkboxes = await page.query_selector_all(checkbox_selector)
            if not checkboxes:
                logger.info("No viewer checkboxes found — may auto-select default")
                return True

            # Select the required number of viewers
            count = min(self.config.event.ticket_count, len(checkboxes))
            for i in range(count):
                if not await checkboxes[i].is_checked():
                    await checkboxes[i].check()
                    await human_delay(100, 300)

            logger.info(f"Selected {count} viewer(s)")
            return True

        except Exception as e:
            logger.warning(f"Viewer selection failed: {e}")
            return False

    async def _check_agreement(self) -> bool:
        """Check the purchase agreement checkbox."""
        page = self.browser.page
        selectors = self.config.selectors.order_page

        agree_selector = selectors.get(
            "agree_checkbox", ".agree-check input[type='checkbox']"
        )

        try:
            agree_el = await page.query_selector(agree_selector)
            if agree_el and not await agree_el.is_checked():
                await agree_el.check()
                logger.info("Agreement checkbox checked")
            return True
        except Exception as e:
            logger.warning(f"Agreement checkbox check failed: {e}")
            return False
