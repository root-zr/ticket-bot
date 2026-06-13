"""Captcha detection and solving orchestration."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from playwright.async_api import Page

from src.config.loader import BotConfig
from src.anti_detect.humanize import human_drag


class CaptchaSolver(ABC):
    """Abstract interface for captcha solving backends."""

    @abstractmethod
    async def solve_slider(self, bg_image: bytes, slider_image: bytes) -> dict:
        """Returns {'x': int} — pixel offset to drag the slider."""
        ...

    @abstractmethod
    async def solve_click_order(self, image: bytes, prompt: str) -> list:
        """Returns list of (x, y) click coordinates in order."""
        ...


class ManualCaptchaSolver(CaptchaSolver):
    """Pauses bot and waits for human to solve captcha in browser."""

    async def solve_slider(self, bg_image: bytes, slider_image: bytes) -> dict:
        logger.warning(
            "⚠️  CAPTCHA detected — switch to headful mode (DAMAI_HEADLESS=false) "
            "to solve manually"
        )
        # In headless mode: just return empty, user must handle manually
        return {"x": 0}

    async def solve_click_order(self, image: bytes, prompt: str) -> list:
        logger.warning("⚠️  Image captcha detected — requires manual solving")
        return []


class TwoCaptchaSolver(CaptchaSolver):
    """2captcha.com API integration — placeholder for future implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def solve_slider(self, bg_image: bytes, slider_image: bytes) -> dict:
        # TODO: Upload images to 2captcha, poll for result, return offset
        logger.warning("2captcha solver not yet implemented")
        return {"x": 0}

    async def solve_click_order(self, image: bytes, prompt: str) -> list:
        # TODO: Upload image with text instruction, poll, return coords
        logger.warning("2captcha solver not yet implemented")
        return []


class CJYSolver(CaptchaSolver):
    """超级鹰 (chaojiying.com) API integration — placeholder."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def solve_slider(self, bg_image: bytes, slider_image: bytes) -> dict:
        # TODO: Implement 超级鹰 API
        logger.warning("超级鹰 solver not yet implemented")
        return {"x": 0}

    async def solve_click_order(self, image: bytes, prompt: str) -> list:
        logger.warning("超级鹰 solver not yet implemented")
        return []


class CaptchaHandler:
    """Orchestrates captcha detection and solving during the buy flow."""

    # Known captcha container selectors on damai.cn
    CAPTCHA_SELECTORS = [
        "#baxia-dialog",           # Alibaba baxia anti-bot
        ".J_MIDDLEWARE",           # Middleware captcha
        "#nc_1_wrapper",           # NoCaptcha slider
        ".captcha-slider",         # Slider captcha
        "iframe[src*='captcha']",  # Captcha iframe
    ]

    def __init__(self, page: Page, solver: CaptchaSolver, notifier=None):
        self.page = page
        self.solver = solver
        self.notifier = notifier

    async def check_and_solve(self) -> bool:
        """Check if a captcha is present. If so, attempt to solve it.

        Returns True if no captcha or captcha was solved successfully.
        """
        for selector in self.CAPTCHA_SELECTORS:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    logger.warning(f"Captcha detected: {selector}")
                    if self.notifier:
                        await self.notifier.send(
                            "验证码出现", f"检测到验证码: {selector}"
                        )
                    return await self._solve_detected_captcha(element, selector)
            except Exception as e:
                logger.debug(f"Selector check failed for {selector}: {e}")

        return True  # No captcha found

    async def _solve_detected_captcha(
        self, container, selector: str
    ) -> bool:
        """Identify captcha type and dispatch to appropriate solver method."""
        # Check for slider (NoCaptcha style)
        slider_handle = await container.query_selector(".nc_iconfont.btn_slide")
        if slider_handle:
            return await self._solve_slider(container, slider_handle)

        # Check for slider (generic style)
        slider_handle2 = await container.query_selector(".slider-btn, .slide-btn")
        if slider_handle2:
            return await self._solve_slider(container, slider_handle2)

        # If captcha is in an iframe, switch context
        if "iframe" in selector:
            return await self._solve_in_iframe(selector)

        # Unknown type: fall back to manual
        logger.warning("Unknown captcha type — requires manual intervention")
        if self.notifier:
            await self.notifier.send("未知验证码", "请切换到 headful 模式手动解决")
        return False

    async def _solve_slider(self, container, slider_handle) -> bool:
        """Solve slider captcha using solver API + human-like drag."""
        # Screenshot background for analysis
        bg_el = await container.query_selector(".nc-bg, .captcha-bg")
        bg_bytes = await bg_el.screenshot() if bg_el else b""
        slider_bytes = await slider_handle.screenshot()

        # Get gap offset from solver
        result = await self.solver.solve_slider(bg_bytes, slider_bytes)
        target_x = result.get("x", 0)

        if target_x > 0:
            # Simulate human drag on the page-level slider
            await human_drag(self.page, slider_handle, target_x)

        # Wait and check if captcha disappeared
        await asyncio.sleep(2)
        try:
            return not await container.is_visible()
        except Exception:
            return True  # Element gone = captcha solved

    async def _solve_in_iframe(self, iframe_selector: str) -> bool:
        """Handle captcha embedded in an iframe."""
        iframe = await self.page.query_selector(iframe_selector)
        if iframe is None:
            return True

        frame = await iframe.content_frame()
        if frame is None:
            return True

        # Look for captcha elements inside iframe
        slider = await frame.query_selector(".nc_iconfont.btn_slide, .slider-btn")
        if slider:
            # Solve within iframe context using the frame's page
            result = await self.solver.solve_slider(b"", b"")
            if result.get("x", 0) > 0:
                # Use the main page for mouse operations (bounding_box coords
                # are relative to the top-level viewport)
                await human_drag(self.page, slider, result["x"])

        await asyncio.sleep(2)
        return True


def create_solver(config: BotConfig) -> CaptchaSolver:
    """Create the appropriate captcha solver based on config."""
    solver_type = config.anti_detect.captcha_solver

    if solver_type == "2captcha":
        return TwoCaptchaSolver(config.anti_detect.captcha_api_key)
    elif solver_type == "cjy":
        return CJYSolver(config.anti_detect.captcha_api_key)
    elif solver_type == "manual":
        return ManualCaptchaSolver()
    else:
        # Default: manual solver
        return ManualCaptchaSolver()
