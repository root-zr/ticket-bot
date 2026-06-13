"""Selector validator — checks that config/selectors.yaml still matches live site.

Usage:
  python -m scripts.selector_validator

This script opens a real browser, navigates to a event page,
and checks whether the CSS selectors defined in selectors.yaml
can actually find elements on the page. Useful for detecting
when 大麦网 has changed their DOM structure.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright

from src.config.loader import load_config
from src.utils.logger import setup_logging
from src.anti_detect.fingerprint import apply_stealth


async def validate_selectors() -> None:
    """Load selectors.yaml and validate each selector against the live site."""
    load_dotenv()
    config = load_config()
    setup_logging(level="DEBUG")

    selectors = config.selectors
    event_url = config.event.url

    if not event_url:
        logger.error("No event URL configured — set DAMAI_EVENT_URL in .env")
        return

    logger.info(f"Validating selectors against: {event_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        await apply_stealth(context)

        page = await context.new_page()

        # Navigate to event page
        try:
            await page.goto(event_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.error(f"Failed to navigate to event page: {e}")
            await browser.close()
            return

        # Validate event_page selectors
        logger.info("── Validating event_page selectors ──")
        event_page = selectors.event_page

        for key, selector in event_page.items():
            # Skip non-selector values (button text strings)
            if any(kw in key for kw in ["text", "class"]):
                continue

            try:
                elements = await page.query_selector_all(selector)
                status = f"✅ Found {len(elements)} element(s)"
            except Exception as e:
                status = f"❌ Error: {e}"

            logger.info(f"  {key}: {selector} → {status}")

        # Validate login selectors (on login page)
        logger.info("── Validating login selectors ──")
        await page.goto("https://passport.damai.cn/login", wait_until="domcontentloaded")

        login = selectors.login
        for key, selector in login.items():
            try:
                element = await page.query_selector(selector)
                visible = await element.is_visible() if element else False
                status = f"✅ Visible" if visible else f"⚠️ Found but not visible" if element else f"❌ Not found"
            except Exception as e:
                status = f"❌ Error: {e}"

            logger.info(f"  {key}: {selector} → {status}")

        # Validate captcha selectors
        logger.info("── Validating captcha selectors ──")
        captcha = selectors.captcha
        for key, selector in captcha.items():
            try:
                element = await page.query_selector(selector)
                status = f"⚠️ Present" if element else f"✅ Not present (expected — captcha only shows on trigger)"
            except Exception as e:
                status = f"❌ Error: {e}"

            logger.info(f"  {key}: {selector} → {status}")

        await browser.close()

    logger.info("Selector validation complete")


if __name__ == "__main__":
    asyncio.run(validate_selectors())
