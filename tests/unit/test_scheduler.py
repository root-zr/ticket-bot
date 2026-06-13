"""Unit tests for CountdownScheduler."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.core.scheduler import CountdownScheduler
from src.config.loader import BotConfig, TimingConfig


class TestCountdownScheduler:
    """Tests for CountdownScheduler."""

    def test_init(self):
        config = BotConfig()
        config.timing.ntp_server = "ntp.example.com"
        config.timing.sale_time = "2026-06-15T10:00:00+08:00"

        scheduler = CountdownScheduler(config)
        assert scheduler.config == config
        assert scheduler._sale_time_iso == "2026-06-15T10:00:00+08:00"

    def _create_mock_ntp(self, offset=0.05, side_effect=None):
        """Create a mock NTPClock with a real float offset."""
        from unittest.mock import patch
        mock = MagicMock()
        mock.offset = 0.05  # Real float, not MagicMock
        if side_effect:
            mock.seconds_until = MagicMock(side_effect=side_effect)
        else:
            mock.seconds_until = MagicMock(return_value=-1)
        return mock

    @pytest.mark.asyncio
    async def test_sale_time_already_past(self):
        """When sale time is past, should return immediately."""
        config = BotConfig()
        config.timing.sale_time = "2020-01-01T00:00:00+00:00"

        with patch("src.core.scheduler.NTPClock") as mock_ntp_cls:
            mock_ntp = self._create_mock_ntp()
            mock_ntp.seconds_until.return_value = -100
            mock_ntp_cls.return_value = mock_ntp

            scheduler = CountdownScheduler(config)
            mock_page = MagicMock()

            await scheduler.wait_until_sale_time(mock_page)
            # Should return immediately without refreshing
            mock_page.reload.assert_not_called()

    @pytest.mark.asyncio
    async def test_coarse_countdown_phase(self):
        """When >5s remaining, should sleep in coarse intervals."""
        config = BotConfig()
        config.timing.sale_time = "2099-01-01T00:00:00+00:00"

        with patch("src.core.scheduler.NTPClock") as mock_ntp_cls:
            mock_ntp = self._create_mock_ntp(
                side_effect=[10, 8, -1]  # >5, >5, past
            )
            mock_ntp_cls.return_value = mock_ntp

            scheduler = CountdownScheduler(config)
            mock_page = MagicMock()

            await scheduler.wait_until_sale_time(mock_page)
            assert mock_ntp.seconds_until.call_count >= 2

    @pytest.mark.asyncio
    async def test_fine_countdown_refreshes_page(self):
        """When <5s remaining, should refresh page frequently."""
        config = BotConfig()
        config.timing.sale_time = "2099-01-01T00:00:00+00:00"

        with patch("src.core.scheduler.NTPClock") as mock_ntp_cls:
            mock_ntp = self._create_mock_ntp(
                side_effect=[3, 2, -0.1]
            )
            mock_ntp_cls.return_value = mock_ntp

            scheduler = CountdownScheduler(config)
            mock_page = MagicMock()
            mock_page.reload = AsyncMock()

            await scheduler.wait_until_sale_time(mock_page)
            assert mock_page.reload.call_count >= 1

    @pytest.mark.asyncio
    async def test_refresh_error_handled(self):
        """Page reload errors should be caught and not break the countdown."""
        config = BotConfig()
        config.timing.sale_time = "2099-01-01T00:00:00+00:00"

        with patch("src.core.scheduler.NTPClock") as mock_ntp_cls:
            mock_ntp = self._create_mock_ntp(
                side_effect=[3, 2, -0.1]
            )
            mock_ntp_cls.return_value = mock_ntp

            scheduler = CountdownScheduler(config)
            mock_page = MagicMock()
            mock_page.reload = AsyncMock(side_effect=Exception("timeout"))

            await scheduler.wait_until_sale_time(mock_page)

    @pytest.mark.asyncio
    async def test_custom_refresh_interval(self):
        """Should use the provided refresh_interval_ms."""
        config = BotConfig()
        config.timing.sale_time = "2099-01-01T00:00:00+00:00"

        with patch("src.core.scheduler.NTPClock") as mock_ntp_cls:
            mock_ntp = self._create_mock_ntp(
                side_effect=[3, -0.1]
            )
            mock_ntp_cls.return_value = mock_ntp

            scheduler = CountdownScheduler(config)
            mock_page = MagicMock()
            mock_page.reload = AsyncMock()

            await scheduler.wait_until_sale_time(mock_page, refresh_interval_ms=200)
            assert mock_page.reload.call_count >= 1
