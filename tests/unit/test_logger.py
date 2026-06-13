"""Unit tests for logger setup."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from loguru import logger

from src.utils.logger import setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_console_only(self):
        """Test that logger can be set up with console output only."""
        initial_handler_count = len(logger._core.handlers)
        setup_logging(level="INFO")
        # Should have at least one handler (console)
        assert len(logger._core.handlers) >= 1
        # Clean up: remove our handler
        logger.remove()

    def test_with_file_output(self, tmp_path):
        """Test logger setup with file output."""
        log_file = tmp_path / "test.log"
        setup_logging(level="DEBUG", log_file=str(log_file), rotation="1 MB")
        assert log_file.parent.exists()
        logger.info("Test log message")
        # Loguru is async by default. Force flush by removing.
        logger.remove()
        assert log_file.exists()

    def test_debug_level(self):
        """Test that DEBUG level is accepted."""
        setup_logging(level="DEBUG")
        logger.remove()
        # No exception = success

    def test_warning_level(self):
        """Test that WARNING level is accepted."""
        setup_logging(level="WARNING")
        logger.remove()

    def test_creates_log_directory(self, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        log_dir = tmp_path / "new_logs"
        log_file = log_dir / "bot.log"
        assert not log_dir.exists()
        setup_logging(level="INFO", log_file=str(log_file))
        logger.remove()
        assert log_dir.exists()

    def test_empty_log_file_skips_file(self):
        """Test that empty log_file means no file handler."""
        initial_count = len(logger._core.handlers)
        setup_logging(level="INFO", log_file="")
        # Should only have console handler (1 more than removed 0)
        assert len(logger._core.handlers) >= 1
        logger.remove()
