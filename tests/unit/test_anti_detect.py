"""Unit tests for anti-detection modules."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.anti_detect.humanize import (
    human_delay,
    human_click,
    generate_drag_path,
    human_scroll,
)
from src.anti_detect.captcha import (
    CaptchaHandler,
    ManualCaptchaSolver,
    TwoCaptchaSolver,
    CJYSolver,
    create_solver,
)
from src.config.loader import BotConfig, AntiDetectConfig
from src.anti_detect.fingerprint import STEALTH_JS, apply_stealth


class TestHumanize:
    """Tests for humanized action utilities."""

    @pytest.mark.asyncio
    async def test_human_delay(self):
        """Test human_delay runs without error."""
        await human_delay(min_ms=10, max_ms=20)

    @pytest.mark.asyncio
    async def test_human_delay_different_ranges(self):
        """Test human_delay with different min/max."""
        await human_delay(min_ms=100, max_ms=200)
        # Should not raise

    def test_generate_drag_path(self):
        """Test Bézier drag path generation."""
        path = generate_drag_path(0, 0, 200, 0, num_steps=10)
        assert len(path) > 0
        # Each point should be (x, y, delay)
        for point in path:
            assert len(point) == 3
            x, y, delay = point
            assert isinstance(x, float)
            assert isinstance(y, float)
            assert isinstance(delay, float)
            assert delay > 0

    def test_generate_drag_path_starts_at_start(self):
        path = generate_drag_path(100, 50, 300, 50, num_steps=5)
        first_x, first_y, _ = path[0]
        assert abs(first_x - 100) < 1  # Start near start_x

    def test_generate_drag_path_includes_correction(self):
        path = generate_drag_path(0, 0, 200, 0, num_steps=10)
        # Should have extra correction steps at the end
        assert len(path) > 10  # includes overshoot + correction steps


class TestStealthFingerprint:
    """Tests for stealth fingerprint module."""

    def test_stealth_js_non_empty(self):
        """STEALTH_JS should contain the core anti-detection patches."""
        assert len(STEALTH_JS) > 0
        assert "webdriver" in STEALTH_JS
        assert "chrome" in STEALTH_JS
        assert "plugins" in STEALTH_JS
        assert "languages" in STEALTH_JS
        assert "WebGL" in STEALTH_JS

    def test_stealth_js_is_function(self):
        """STEALTH_JS should be an arrow function."""
        assert "() => {" in STEALTH_JS

    @pytest.mark.asyncio
    async def test_apply_stealth(self):
        """Test that apply_stealth calls add_init_script."""
        mock_context = MagicMock()
        mock_context.add_init_script = AsyncMock()

        await apply_stealth(mock_context)

        mock_context.add_init_script.assert_called_once_with(STEALTH_JS)


class TestCaptchaSolvers:
    """Tests for captcha solver implementations."""

    def test_create_solver_none_returns_manual(self):
        config = BotConfig()
        config.anti_detect.captcha_solver = "none"
        solver = create_solver(config)
        assert isinstance(solver, ManualCaptchaSolver)

    def test_create_solver_manual(self):
        config = BotConfig()
        config.anti_detect.captcha_solver = "manual"
        solver = create_solver(config)
        assert isinstance(solver, ManualCaptchaSolver)

    def test_create_solver_2captcha(self):
        config = BotConfig()
        config.anti_detect.captcha_solver = "2captcha"
        config.anti_detect.captcha_api_key = "test_key"
        solver = create_solver(config)
        assert isinstance(solver, TwoCaptchaSolver)
        assert solver.api_key == "test_key"

    def test_create_solver_cjy(self):
        config = BotConfig()
        config.anti_detect.captcha_solver = "cjy"
        config.anti_detect.captcha_api_key = "test_key"
        solver = create_solver(config)
        assert isinstance(solver, CJYSolver)
        assert solver.api_key == "test_key"

    @pytest.mark.asyncio
    async def test_manual_solver_slider(self):
        solver = ManualCaptchaSolver()
        result = await solver.solve_slider(b"", b"")
        assert result == {"x": 0}

    @pytest.mark.asyncio
    async def test_manual_solver_click_order(self):
        solver = ManualCaptchaSolver()
        result = await solver.solve_click_order(b"", "")
        assert result == []

    @pytest.mark.asyncio
    async def test_2captcha_solver_placeholder(self):
        solver = TwoCaptchaSolver("key123")
        result = await solver.solve_slider(b"", b"")
        assert result == {"x": 0}  # Placeholder

    @pytest.mark.asyncio
    async def test_cjy_solver_placeholder(self):
        solver = CJYSolver("key456")
        result = await solver.solve_click_order(b"", "")
        assert result == []  # Placeholder


class TestCaptchaHandler:
    """Tests for CaptchaHandler."""

    @pytest.mark.asyncio
    async def test_check_no_captcha(self):
        mock_page = MagicMock()
        # No captcha selectors found
        mock_page.query_selector = AsyncMock(return_value=None)

        solver = ManualCaptchaSolver()
        handler = CaptchaHandler(mock_page, solver)

        result = await handler.check_and_solve()
        assert result is True  # No captcha = success

    @pytest.mark.asyncio
    async def test_known_selectors(self):
        """Verify the handler knows about expected captcha selectors."""
        solver = ManualCaptchaSolver()
        handler = CaptchaHandler(None, solver)

        assert "#baxia-dialog" in handler.CAPTCHA_SELECTORS
        assert ".J_MIDDLEWARE" in handler.CAPTCHA_SELECTORS
        assert "#nc_1_wrapper" in handler.CAPTCHA_SELECTORS
        assert ".captcha-slider" in handler.CAPTCHA_SELECTORS
        assert any("iframe" in s for s in handler.CAPTCHA_SELECTORS)

    @pytest.mark.asyncio
    async def test_check_with_invisible_captcha(self):
        mock_page = MagicMock()
        mock_el = MagicMock()
        mock_el.is_visible = AsyncMock(return_value=False)
        mock_page.query_selector = AsyncMock(return_value=mock_el)

        solver = ManualCaptchaSolver()
        handler = CaptchaHandler(mock_page, solver)

        result = await handler.check_and_solve()
        assert result is True  # Invisible captcha = no captcha

    @pytest.mark.asyncio
    async def test_check_selector_error_graceful(self):
        mock_page = MagicMock()
        mock_page.query_selector = AsyncMock(side_effect=Exception("DOM error"))

        solver = ManualCaptchaSolver()
        handler = CaptchaHandler(mock_page, solver)

        result = await handler.check_and_solve()
        assert result is True  # Error = assume no captcha
