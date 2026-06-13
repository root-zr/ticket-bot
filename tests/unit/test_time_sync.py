"""Unit tests for time synchronization utilities."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from src.utils.time_sync import NTPClock


class MockNTPResponse:
    """Mock NTP response object."""
    def __init__(self, offset=0.05):
        self.offset = offset


class TestNTPClock:
    """Tests for NTPClock."""

    def test_sync_success(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.1234)
            mock_client_class.return_value = mock_client

            clock = NTPClock(server="ntp.example.com")

            assert clock.server == "ntp.example.com"
            assert clock.offset == pytest.approx(0.1234)

    def test_sync_failure_fallback(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.side_effect = OSError("Network error")
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            # Should fall back to offset=0
            assert clock.offset == 0.0

    def test_sync_default_server(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            assert clock.server == "ntp.aliyun.com"

    def test_now_returns_datetime(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            now = clock.now()
            assert isinstance(now, datetime)
            assert now.tzinfo == timezone.utc

    def test_now_cst(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            cst_now = clock.now_cst()
            assert isinstance(cst_now, datetime)
            # CST is UTC+8
            cst_offset = cst_now.utcoffset()
            assert cst_offset == timedelta(hours=8)

    def test_seconds_until_past_time(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            # Set offset to make "now" appear 100 seconds ahead
            mock_client.request.return_value = MockNTPResponse(offset=100.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            # Target is roughly "now" without the offset, so ~100s in the past
            target = datetime.now(timezone.utc) + timedelta(seconds=50)
            target_iso = target.isoformat()

            remaining = clock.seconds_until(target_iso)
            # Should be negative (time already passed from NTP perspective)
            assert remaining < 0

    def test_seconds_until_future_time(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            # Target 100 seconds in the future
            target = datetime.now(timezone.utc) + timedelta(seconds=100)
            target_iso = target.isoformat()

            remaining = clock.seconds_until(target_iso)
            assert 95 < remaining < 105  # Allow small timing variance

    def test_seconds_until_with_tz(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            # Explicit timezone (CST = UTC+8)
            target_iso = "2026-06-15T10:00:00+08:00"
            remaining = clock.seconds_until(target_iso)
            assert isinstance(remaining, float)

    def test_seconds_until_without_tz_assumes_cst(self):
        with patch("src.utils.time_sync.ntplib.NTPClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = MockNTPResponse(offset=0.0)
            mock_client_class.return_value = mock_client

            clock = NTPClock()
            # No timezone specified — should assume CST
            target_iso = "2026-06-15T10:00:00"
            remaining = clock.seconds_until(target_iso)
            assert isinstance(remaining, float)
