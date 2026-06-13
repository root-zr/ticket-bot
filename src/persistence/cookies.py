"""Cookie persistence — save/load Playwright storage state as JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from loguru import logger


class CookieStore:
    """Manages browser cookie persistence via Playwright storage state.

    Storage state includes cookies and localStorage, saved as a JSON file.
    This allows login sessions to persist across bot runs.
    """

    def __init__(self, path: str = "data/cookies/damai_cookies.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: dict) -> str:
        """Save storage state dict to JSON file.

        Args:
            state: Playwright storage state dict (cookies + origins).

        Returns:
            Path to saved file.
        """
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookie state saved to: {self.path}")
        return str(self.path)

    def load(self) -> Optional[dict]:
        """Load storage state from JSON file.

        Returns:
            Storage state dict, or None if file doesn't exist.
        """
        if not self.path.exists():
            logger.info("No saved cookies found — will need to login")
            return None

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info(f"Cookie state loaded from: {self.path}")
            return state
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
            return None

    def exists(self) -> bool:
        """Check if saved cookies exist."""
        return self.path.exists()

    def delete(self) -> None:
        """Delete saved cookies file."""
        if self.path.exists():
            self.path.unlink()
            logger.info("Cookie file deleted")

    def is_expired(self, max_age_days: int = 7) -> bool:
        """Check if cookie file is older than max_age_days.

        Args:
            max_age_days: Maximum acceptable age in days.
        """
        if not self.path.exists():
            return True

        import time
        file_age = time.time() - self.path.stat().st_mtime
        return file_age > max_age_days * 86400
