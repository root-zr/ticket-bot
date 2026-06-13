"""Unit tests for retry utilities."""

from __future__ import annotations

import asyncio

import pytest

from src.core.retry import retry_with_backoff, RetryPolicy


class TestRetryPolicy:
    """Tests for RetryPolicy dataclass."""

    def test_default_construction(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay_ms == 500
        assert policy.max_delay_ms == 3000
        assert policy.backoff_multiplier == 1.5
        assert policy.jitter is True
        assert policy.retryable == (Exception,)

    def test_custom_construction(self):
        policy = RetryPolicy(
            max_attempts=5,
            base_delay_ms=100,
            max_delay_ms=500,
            backoff_multiplier=2.0,
            jitter=False,
            retryable=(ValueError, KeyError),
        )
        assert policy.max_attempts == 5
        assert policy.base_delay_ms == 100
        assert policy.backoff_multiplier == 2.0
        assert policy.jitter is False
        assert policy.retryable == (ValueError, KeyError)


class TestRetryDecorator:
    """Tests for retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay_ms=10)
        async def succeed_on_first():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeed_on_first()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_and_succeed(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay_ms=10, jitter=False)
        async def succeed_on_third():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "finally"

        result = await succeed_on_third()
        assert result == "finally"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay_ms=10, jitter=False)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("persistent error")

        with pytest.raises(RuntimeError, match="persistent error"):
            await always_fails()
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        call_count = 0

        @retry_with_backoff(
            max_attempts=3, base_delay_ms=10, retryable=(ValueError,)
        )
        async def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("non-retryable")

        with pytest.raises(TypeError):
            await raises_type_error()
        assert call_count == 1  # Should NOT retry

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        @retry_with_backoff(max_attempts=3, base_delay_ms=10)
        async def with_args(a, b, c=None):
            return a + b + (c or 0)

        result = await with_args(1, 2, c=3)
        assert result == 6

    @pytest.mark.asyncio
    async def test_decorator_preserves_metadata(self):
        @retry_with_backoff(max_attempts=3, base_delay_ms=10)
        async def my_function():
            """Custom docstring."""
            return True

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "Custom docstring."
