"""Screenshot manager — captures page screenshots on errors and key milestones."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import Page


class ScreenshotManager:
    """Manages automatic screenshot capture for debugging and notifications."""

    def __init__(self, screenshot_dir: str = "data/screenshots"):
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def capture(
        self,
        page: Page,
        label: str,
        full_page: bool = True,
    ) -> Optional[str]:
        """Capture a screenshot and save to disk.

        Args:
            page: Playwright page to screenshot.
            label: Descriptive label for the screenshot file name.
            full_page: Whether to capture the full scrollable page.

        Returns:
            Path to saved screenshot, or None on failure.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{label}.png"
            filepath = self.screenshot_dir / filename

            await page.screenshot(path=str(filepath), full_page=full_page)
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}")
            return None
