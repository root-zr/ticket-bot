"""Unit tests for CookieStore persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.persistence.cookies import CookieStore


class TestCookieStore:
    """Tests for CookieStore."""

    def test_save_and_load(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        store = CookieStore(str(cookie_file))

        state = {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc123",
                    "domain": ".damai.cn",
                }
            ],
            "origins": [],
        }

        path = store.save(state)
        assert Path(path).exists()
        assert cookie_file.exists()

        loaded = store.load()
        assert loaded is not None
        assert loaded["cookies"][0]["name"] == "session"
        assert loaded["cookies"][0]["value"] == "abc123"

    def test_load_nonexistent_file(self, tmp_path):
        store = CookieStore(str(tmp_path / "nonexistent.json"))
        result = store.load()
        assert result is None

    def test_exists(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        store = CookieStore(str(cookie_file))
        assert store.exists() is False

        store.save({"cookies": []})
        assert store.exists() is True

    def test_delete(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        store = CookieStore(str(cookie_file))
        store.save({"cookies": []})
        assert store.exists() is True

        store.delete()
        assert store.exists() is False

    def test_is_expired(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        store = CookieStore(str(cookie_file))

        # Non-existent file is "expired"
        assert store.is_expired() is True

        # Fresh file is not expired
        store.save({"cookies": []})
        assert store.is_expired(max_age_days=7) is False

    def test_is_expired_custom_age(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        store = CookieStore(str(cookie_file))

        # Save and check with max_age_days=1 (very permissive)
        store.save({"cookies": []})
        # File was just created, should not be expired
        assert store.is_expired(max_age_days=1) is False

    def test_creates_parent_directory(self, tmp_path):
        nested_path = tmp_path / "deep" / "nested" / "cookies.json"
        store = CookieStore(str(nested_path))
        store.save({"cookies": []})
        assert nested_path.exists()

    def test_load_corrupted_file(self, tmp_path):
        cookie_file = tmp_path / "corrupted.json"
        cookie_file.write_text("not valid json {{{")
        store = CookieStore(str(cookie_file))
        result = store.load()
        assert result is None

    def test_save_unicode_content(self, tmp_path):
        cookie_file = tmp_path / "unicode.json"
        store = CookieStore(str(cookie_file))
        state = {"cookies": [{"name": "用户名", "value": "中文值"}]}
        store.save(state)

        loaded = store.load()
        assert loaded["cookies"][0]["name"] == "用户名"
        assert loaded["cookies"][0]["value"] == "中文值"
