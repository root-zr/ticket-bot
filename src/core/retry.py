"""Retry utilities — decorator with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
import functools
from typing import Type, Tuple, Callable, Any

from loguru import logger


class RetryPolicy:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_ms: int = 500,
        max_delay_ms: int = 3000,
        backoff_multiplier: float = 1.5,
        jitter: bool = True,
        retryable: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.retryable = retryable


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay_ms: int = 500,
    max_delay_ms: int = 3000,
    backoff_multiplier: float = 1.5,
    jitter: bool = True,
    retryable: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator that retries an async function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay_ms: Initial delay in milliseconds.
        max_delay_ms: Maximum delay cap in milliseconds.
        backoff_multiplier: Multiplier for each successive delay.
        jitter: Whether to add random jitter to delays.
        retryable: Exception types that trigger a retry.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable as e:
                    last_exception = e
                    if attempt >= max_attempts:
                        logger.error(
                            f"Retry exhausted after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay_ms = min(
                        base_delay_ms * (backoff_multiplier ** (attempt - 1)),
                        max_delay_ms,
                    )
                    if jitter:
                        delay_ms = random.uniform(delay_ms * 0.5, delay_ms * 1.5)

                    delay_s = delay_ms / 1000
                    logger.warning(
                        f"Retry {attempt}/{max_attempts} after {delay_s:.2f}s — {e}"
                    )
                    await asyncio.sleep(delay_s)

            # Should not reach here, but just in case
            raise last_exception

        return wrapper

    return decorator
