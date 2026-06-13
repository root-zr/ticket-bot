"""Unit tests for SnatcherStateMachine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.snatcher import SnatcherStateMachine, State
from src.config.loader import BotConfig


@pytest.fixture
def mock_config():
    config = BotConfig()
    config.event.url = "https://detail.damai.cn/item.htm?id=12345"
    config.event.ticket_count = 1
    config.timing.sale_time = "2099-01-01T00:00:00+00:00"
    config.retry.max_attempts = 3
    return config


@pytest.fixture
def mock_browser():
    browser = MagicMock()
    browser.start = AsyncMock()
    browser.close = AsyncMock()
    browser.save_storage_state = AsyncMock()
    browser.page = MagicMock()
    return browser


@pytest.fixture
def mock_scheduler():
    scheduler = MagicMock()
    scheduler.wait_until_sale_time = AsyncMock()
    return scheduler


@pytest.fixture
def mock_notifier():
    notifier = MagicMock()
    notifier.send = AsyncMock()
    return notifier


@pytest.fixture
def mock_snatcher(mock_browser, mock_scheduler, mock_notifier, mock_config):
    """Create a SnatcherStateMachine with mocked dependencies."""
    sm = SnatcherStateMachine(mock_browser, mock_scheduler, mock_notifier, mock_config)
    return sm


class TestStates:
    """Tests for State enum."""

    def test_all_states_defined(self):
        """Verify all expected states exist."""
        expected = {
            "init", "logging_in", "logged_in", "navigating",
            "waiting_for_sale", "selecting_ticket", "submitting_order",
            "payment_pending", "done", "failed",
        }
        actual = {s.value for s in State}
        assert actual == expected

    def test_terminal_states(self):
        """DONE and FAILED are terminal states."""
        assert State.DONE.value == "done"
        assert State.FAILED.value == "failed"


class TestSnatcherStateMachineInit:
    """Tests for initialization."""

    def test_initial_state(self, mock_snatcher):
        assert mock_snatcher.state == State.INIT

    def test_initial_attempt_zero(self, mock_snatcher):
        assert mock_snatcher.attempt == 0

    def test_max_attempts_from_config(self, mock_snatcher):
        assert mock_snatcher.max_attempts == 3

    def test_components_stored(self, mock_snatcher, mock_browser, mock_scheduler, mock_notifier):
        assert mock_snatcher.browser == mock_browser
        assert mock_snatcher.scheduler == mock_scheduler
        assert mock_snatcher.notifier == mock_notifier


class TestStateMachineHandlers:
    """Tests for individual state handlers."""

    @pytest.mark.asyncio
    async def test_handle_init(self, mock_snatcher):
        """INIT should start browser and transition to LOGGING_IN."""
        state = await mock_snatcher._handle_init()
        mock_snatcher.browser.start.assert_called_once()
        mock_snatcher.notifier.send.assert_called_once()
        assert state == State.LOGGING_IN

    @pytest.mark.asyncio
    async def test_handle_wait_for_sale(self, mock_snatcher):
        """WAIT_FOR_SALE should call scheduler and transition to SELECTING_TICKET."""
        state = await mock_snatcher._handle_wait_for_sale()
        mock_snatcher.scheduler.wait_until_sale_time.assert_called_once()
        mock_snatcher.notifier.send.assert_called_once()
        assert state == State.SELECTING_TICKET

    @pytest.mark.asyncio
    async def test_handle_error_with_retries(self, mock_snatcher):
        """Error handler should return SELECTING_TICKET if attempts remain."""
        mock_snatcher.state = State.SELECTING_TICKET
        state = await mock_snatcher._handle_error(Exception("timeout"))
        assert state == State.SELECTING_TICKET

    @pytest.mark.asyncio
    async def test_handle_error_no_retries(self, mock_snatcher):
        """Error handler should return FAILED if max attempts reached."""
        mock_snatcher.attempt = 5
        mock_snatcher.max_attempts = 3
        state = await mock_snatcher._handle_error(Exception("fatal"))
        assert state == State.FAILED


class TestStateMachineRun:
    """Tests for the run() method."""

    @pytest.mark.asyncio
    async def test_run_successful_flow(self, mock_snatcher, mock_config):
        """Test a complete successful state machine run."""
        # Make antidetect config non-stealth to simplify
        mock_config.anti_detect.stealth_mode = False

        # Patch the action handlers
        with patch.object(mock_snatcher, '_handle_init', new=AsyncMock(return_value=State.LOGGING_IN)):
            with patch.object(mock_snatcher, '_handle_login', new=AsyncMock(return_value=State.LOGGED_IN)):
                with patch.object(mock_snatcher, '_handle_navigate', new=AsyncMock(return_value=State.WAITING_FOR_SALE)):
                    with patch.object(mock_snatcher, '_handle_wait_for_sale', new=AsyncMock(return_value=State.SELECTING_TICKET)):
                        with patch.object(mock_snatcher, '_handle_select_ticket', new=AsyncMock(return_value=State.SUBMITTING_ORDER)):
                            with patch.object(mock_snatcher, '_handle_submit_order', new=AsyncMock(return_value=State.PAYMENT_PENDING)):
                                with patch.object(mock_snatcher, '_handle_payment', new=AsyncMock(return_value=State.DONE)):
                                    final_state = await mock_snatcher.run()

        assert final_state == State.DONE

    @pytest.mark.asyncio
    async def test_run_login_fails(self, mock_snatcher, mock_config):
        """If login fails, should end in FAILED state."""
        mock_config.anti_detect.stealth_mode = False

        with patch.object(mock_snatcher, '_handle_init', new=AsyncMock(return_value=State.LOGGING_IN)):
            with patch.object(mock_snatcher, '_handle_login', new=AsyncMock(side_effect=RuntimeError("Login failed"))):
                with patch.object(mock_snatcher, '_handle_error', new=AsyncMock(return_value=State.FAILED)):
                    final_state = await mock_snatcher.run()

        assert final_state == State.FAILED
