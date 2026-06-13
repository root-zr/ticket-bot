"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is in sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove environment variables that could affect tests."""
    for key in list(os.environ.keys()):
        if key.startswith("DAMAI_") or key.startswith("CAPTCHA_") or key.startswith("WECHAT_") or key.startswith("DINGTALK_") or key.startswith("TELEGRAM_") or key.startswith("BARK_"):
            monkeypatch.delenv(key, raising=False)
