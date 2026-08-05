"""Async execution of retry and per-attempt timeout policies."""

import asyncio
from collections.abc import Awaitable, Callable

from setuper.domain.errors import ReadinessTimeoutError
from setuper.domain.models import RetrySpec
from setuper.domain.policies import compute_retry_delay, total_attempts


async def run_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    retry: RetrySpec | None,
    timeout_seconds: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run one async operation with a per-attempt timeout and retry backoff."""
    attempts = total_attempts(retry)
    for attempt in range(1, attempts + 1):
        is_last_attempt = attempt == attempts
        try:
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except TimeoutError as error:
            if is_last_attempt:
                raise ReadinessTimeoutError(
                    f"Operation did not complete within {timeout_seconds}s "
                    f"(attempt {attempt}/{attempts})",
                    details={"attempt": attempt, "attempts": attempts},
                ) from error
        except Exception:
            if is_last_attempt:
                raise
        if retry is not None:
            await sleep(compute_retry_delay(retry, attempt))
    raise RuntimeError("unreachable: retry attempts is always at least 1")
