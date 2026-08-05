"""Tests for async retry-with-timeout execution."""

import asyncio

import pytest

from setuper.domain.errors import ReadinessTimeoutError
from setuper.domain.models import RetrySpec
from setuper.infrastructure.retry import run_with_retry


class _FakeSleep:
    """Recording no-op sleep replacing real delays in tests."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        """Record a requested delay without actually waiting."""
        self.delays.append(delay)


def _retry_spec(attempts: int) -> RetrySpec:
    """Build a fast-backoff retry policy for deterministic tests."""
    return RetrySpec(
        attempts=attempts,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=10.0,
        backoff=2.0,
    )


def test_run_with_retry_returns_immediately_on_first_success() -> None:
    """A successful first attempt needs no retries or sleeps."""

    async def scenario() -> None:
        sleep = _FakeSleep()

        async def operation() -> str:
            return "ok"

        result = await run_with_retry(
            operation,
            retry=_retry_spec(3),
            timeout_seconds=1.0,
            sleep=sleep,
        )

        assert result == "ok"
        assert sleep.delays == []

    asyncio.run(scenario())


def test_run_with_retry_retries_after_failures_then_succeeds() -> None:
    """Failures before the final attempt are retried with backoff delays."""

    async def scenario() -> None:
        sleep = _FakeSleep()
        remaining_failures = [RuntimeError("boom"), RuntimeError("boom again")]

        async def operation() -> str:
            if remaining_failures:
                raise remaining_failures.pop(0)
            return "ok"

        result = await run_with_retry(
            operation,
            retry=_retry_spec(3),
            timeout_seconds=1.0,
            sleep=sleep,
        )

        assert result == "ok"
        assert sleep.delays == [1.0, 2.0]

    asyncio.run(scenario())


def test_run_with_retry_reraises_original_error_after_exhausting_attempts() -> None:
    """Once every attempt fails, the last real error propagates unchanged."""

    async def scenario() -> None:
        sleep = _FakeSleep()

        async def operation() -> str:
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            await run_with_retry(
                operation,
                retry=_retry_spec(3),
                timeout_seconds=1.0,
                sleep=sleep,
            )

        assert sleep.delays == [1.0, 2.0]

    asyncio.run(scenario())


def test_run_with_retry_wraps_timeout_as_typed_error_on_last_attempt() -> None:
    """A per-attempt timeout on the final attempt becomes ReadinessTimeoutError."""

    async def scenario() -> None:
        sleep = _FakeSleep()

        async def operation() -> str:
            await asyncio.sleep(10)
            return "unreachable"

        with pytest.raises(ReadinessTimeoutError):
            await run_with_retry(
                operation,
                retry=_retry_spec(2),
                timeout_seconds=0.05,
                sleep=sleep,
            )

        assert sleep.delays == [1.0]

    asyncio.run(scenario())


def test_run_with_retry_without_a_retry_policy_makes_one_attempt() -> None:
    """No retry policy means a single attempt and no sleeping between tries."""

    async def scenario() -> None:
        sleep = _FakeSleep()
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await run_with_retry(
                operation,
                retry=None,
                timeout_seconds=1.0,
                sleep=sleep,
            )

        assert calls == 1
        assert sleep.delays == []

    asyncio.run(scenario())
