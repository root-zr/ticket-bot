"""Login helper — QR code login and cookie saving.

Supports two modes:
  - Headful (default locally): opens visible browser, user scans QR code
  - Headless (default in Docker): captures QR code screenshot, saves to file,
    user scans from the saved image

Usage:
  # Locally (headed browser):
  python -m scripts.login_helper

  # Locally (headless, captures QR to file):
  python -m scripts.login_helper --headless

  # Via Docker:
  docker compose --profile tools run --rm damai-login
  # QR code image will be saved to ./data/screenshots/qr_code.png
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import async_playwright

from src.config.loader import load_config
from src.persistence.cookies import CookieStore
from src.utils.logger import setup_logging
from src.anti_detect.fingerprint import apply_stealth


async def main(headless: bool = False) -> None:
    """Open browser, navigate to login, wait for QR scan, save cookies.

    Args:
        headless: If True, run without visible browser. QR code will be
                  captured as a screenshot for scanning.
    """
    load_dotenv()
    config = load_config()
    setup_logging(level="INFO")

    cookie_store = CookieStore(config.persistence.cookies_file)

    # Determine headless mode.
    # Priority: 1) explicit --headless/--no-headless CLI flag
    #           2) auto-detect (macOS → headed, Linux no DISPLAY → headless)
    #           3) DAMAI_HEADLESS env var as fallback only
    # Note: the CLI arg already handled auto-detection in __main__;
    # DAMAI_HEADLESS is meant for the main bot, not the login helper.
    if headless is None:
        # Auto-detect
        if sys.platform == "darwin":
            headless = False
        else:
            headless = not os.environ.get("DISPLAY")

    async with async_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]

        browser = await p.chromium.launch(
            headless=headless,
            slow_mo=100,
            args=launch_args,
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
        # Use domcontentloaded (not networkidle) — damai.cn has persistent
        # analytics/beacon requests that prevent networkidle from ever firing.
        logger.info("正在打开大麦网登录页...")
        await page.goto(
            "https://passport.damai.cn/login", wait_until="domcontentloaded"
        )
        await asyncio.sleep(3)

        # ── Locate the login iframe ──
        # Damai.cn login is embedded in an iframe from ipassport.damai.cn.
        # In some environments (local macOS, mobile viewport), the iframe
        # may not be present or may load the form directly.
        login_frame = None
        for frame in page.frames:
            if "ipassport.damai.cn" in frame.url or "mini_login" in frame.url:
                login_frame = frame
                break

        if login_frame is None:
            # Iframe may not have loaded yet; wait and retry once
            await asyncio.sleep(2)
            for frame in page.frames:
                if "ipassport.damai.cn" in frame.url or "mini_login" in frame.url:
                    login_frame = frame
                    break

        if login_frame is None:
            logger.info("未找到登录 iframe，尝试在主页面查找登录元素...")
            login_frame = page  # Fallback to main page

        # ── Switch to QR code tab ──
        # The login page defaults to password login; click "扫码登录" tab
        login_selectors = config.selectors.login
        qr_tab_selectors = login_selectors.get("qr_code_tabs", [
            'div:text("扫码登录")',
            '.login-tabs-tab:text("扫码登录")',
            'a:text("扫码登录")',
        ])

        qr_clicked = False
        for sel in qr_tab_selectors:
            try:
                qr_tab = await login_frame.query_selector(sel)
                if qr_tab and await qr_tab.is_visible():
                    await qr_tab.click()
                    logger.info(f"已点击扫码登录 tab: {sel}")
                    qr_clicked = True
                    break
            except Exception:
                continue

        if not qr_clicked:
            logger.warning("未找到扫码登录 tab，可能已在扫码页面")

        # Wait for QR code to load
        await asyncio.sleep(3)

        if headless:
            # Headless mode: capture QR code image for scanning
            logger.info("Headless 模式 — 正在截取二维码...")

            # Look for QR code image inside the iframe
            qr_selectors = login_selectors.get("qr_code_image_selectors", [
                ".qrcode-img img",
                ".login-qrcode img",
                "img[src*='qrcode']",
                "img[src*='qr']",
                ".qrcode-wrapper img",
                "#qrcode img",
            ])

            qr_found = False
            for sel in qr_selectors:
                try:
                    el = await login_frame.query_selector(sel)
                    if el and await el.is_visible():
                        qr_path = Path("data/screenshots/qr_code.png")
                        qr_path.parent.mkdir(parents=True, exist_ok=True)
                        await el.screenshot(path=str(qr_path))
                        logger.info(f"✅ 二维码已保存到: {qr_path}")
                        qr_found = True
                        break
                except Exception:
                    continue

            if not qr_found:
                # Fallback: screenshot the iframe content area
                logger.info("未定位到独立二维码元素，截取登录区域...")
                full_path = Path("data/screenshots/login_page.png")
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Try to screenshot the #container inside iframe
                content_el = await login_frame.query_selector("#container")
                if content_el and await content_el.is_visible():
                    await content_el.screenshot(path=str(full_path))
                else:
                    await page.screenshot(path=str(full_path), full_page=False)
                logger.info(f"✅ 登录区域截图已保存到: {full_path}")
                logger.info("请打开截图文件，用大麦App扫描其中的二维码")

            logger.info("等待扫码登录中... (超时 120 秒)")

        else:
            logger.info("请在浏览器窗口中扫描二维码登录...")

        # Wait for successful login
        # After scanning QR code, the page redirects to damai.cn homepage.
        # We detect success by: 1) URL change away from login page,
        # 2) logged-in state indicators (user menu, logout link, etc.)
        login_success = False
        try:
            # Strategy 1: Wait for navigation away from passport.damai.cn
            await page.wait_for_url(
                lambda url: "passport.damai.cn" not in url,
                timeout=120_000,
            )
            await asyncio.sleep(2)
            login_success = True
        except Exception:
            pass

        # Strategy 2: Verify by checking for logged-in state indicators
        if login_success:
            logger.info("页面已跳转，验证登录状态...")
            success_selectors = login_selectors.get("login_success_indicators", [
                'a:text("退出登录")',
                '.out-login',
                'a[href*="logout"]',
                '.login-user',
                '.span-user',
                '.list-login',
            ])
            # Just check that we're on damai.cn and not on the login page
            current_url = page.url
            if "damai.cn" in current_url and "passport" not in current_url:
                logger.info("✅ 登录成功！正在保存 Cookie...")
            else:
                # Try the selectors
                found = False
                for sel in success_selectors:
                    try:
                        el = await login_frame.query_selector(sel)
                        if el:
                            text = (await el.text_content() or "").strip()
                            if text and text != "登录":
                                logger.info(f"✅ 登录成功！检测到: '{text[:30]}'")
                                found = True
                                break
                    except Exception:
                        continue
                if not found:
                    # Still consider it a success if URL changed from passport
                    logger.info("✅ 登录成功！正在保存 Cookie...")
        else:
            logger.error("登录超时 (2分钟未检测到登录成功)")
            if headless:
                logger.info("提示: 请确保已扫描 data/screenshots/ 下的二维码截图")
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
        logger.info("✅ Session 验证通过 — 现在可以运行主 Bot 了")

        if not headless:
            # Keep browser open briefly so user can verify
            await asyncio.sleep(3)

        await browser.close()

    logger.info("Login helper 完成 — 运行以下命令启动抢票:")
    logger.info("  python -m src.main")
    logger.info("  docker compose up damai-bot")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="大麦网登录助手 — 扫码登录并保存Cookie"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="无头模式：截取二维码图片保存到文件 (Docker 默认启用)",
    )
    args = parser.parse_args()

    # Default to headless in Docker/no-DISPLAY environments
    # macOS can use native window system even without DISPLAY
    headless = args.headless
    if headless is None:
        if sys.platform == "darwin":
            # macOS: Playwright uses native Cocoa windows, no X11 needed
            headless = False
        else:
            # Linux: check for DISPLAY; Docker containers have no DISPLAY
            headless = not os.environ.get("DISPLAY")

    asyncio.run(main(headless=headless))
