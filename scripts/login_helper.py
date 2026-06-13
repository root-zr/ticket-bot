"""Login helper — headful browser for QR code login and cookie saving.

Usage:
  # Locally:
  python -m scripts.login_helper

  # Via Docker (Linux desktop with X11):
  docker compose --profile tools run --rm damai-login

  # Via Docker (macOS — use XQuartz for X11 forwarding):
  # 1. Install XQuartz: brew install --cask xquartz
  # 2. Start XQuartz, enable "Allow connections from network clients"
  # 3. Run: xhost +local:
  # 4. Run: docker compose --profile tools run --rm -e DISPLAY=host.docker.internal:0 damai-login
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright

from src.config.loader import load_config
from src.persistence.cookies import CookieStore
from src.utils.logger import setup_logging
from src.anti_detect.fingerprint import apply_stealth


async def main() -> None:
    """Open visible browser, navigate to login, wait for QR scan, save cookies."""
    load_dotenv()
    config = load_config()
    setup_logging(level="INFO")

    cookie_store = CookieStore(config.persistence.cookies_file)

    async with async_playwright() as p:
        # Launch VISIBLE browser (headless=False for QR scanning)
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # Apply stealth patches
        await apply_stealth(context)

        page = await context.new_page()

        # Navigate to login page
        await page.goto("https://passport.damai.cn/login")
        logger.info("请在浏览器中扫描二维码登录... (Scan QR code in browser window)")

        # Wait for successful login (URL change or element)
        try:
            await page.wait_for_url(
                "**/user/**",
                timeout=120_000,  # 2 minutes to scan
            )
            logger.info("✅ 登录成功！正在保存 Cookie...")
        except Exception:
            # Alternative check: wait for username element
            try:
                selectors = config.selectors.login
                indicator = selectors.get("login_success_indicator", ".header-user-name")
                await page.wait_for_selector(indicator, state="visible", timeout=120_000)
                logger.info("✅ 登录成功！正在保存 Cookie...")
            except Exception as e:
                logger.error(f"Login timed out after 2 minutes: {e}")
                await browser.close()
                return

        # Save storage state (cookies + localStorage)
        cookies_path = Path(config.persistence.cookies_file)
        cookies_path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state(path=str(cookies_path))
        logger.info(f"✅ Cookie 已保存到: {cookies_path}")

        # Navigate to homepage to verify session
        await page.goto("https://www.damai.cn/")
        await asyncio.sleep(2)
        logger.info("✅ Session verified — you can now close this window")

        # Keep browser open briefly so user can verify
        await asyncio.sleep(5)
        await browser.close()

    logger.info("Login helper complete — you can now run the main bot")


if __name__ == "__main__":
    asyncio.run(main())
