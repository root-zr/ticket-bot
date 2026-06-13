"""Logging setup using loguru — structured logs with rotation."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(level: str = "INFO", log_file: str = "", rotation: str = "10 MB") -> None:
    """Configure loguru logger with console + optional file output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Path pattern for log file. Empty = no file logging.
                  Supports loguru time placeholders like {time}.
        rotation: File rotation condition (e.g. "10 MB", "1 day").
    """
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
               "<level>{message}</level>",
    )

    # File handler (if configured)
    if log_file:
        # Ensure log directory exists
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=level,
            rotation=rotation,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
            encoding="utf-8",
        )

    logger.info(f"Logging initialized — level={level}")
