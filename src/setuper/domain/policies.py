"""Pure retry backoff and attempt-count policy calculations."""

from setuper.domain.models import RetrySpec


def total_attempts(retry: RetrySpec | None) -> int:
    """Return the total attempt count for an optional retry policy."""
    return retry.attempts if retry is not None else 1


def compute_retry_delay(retry: RetrySpec, attempt: int) -> float:
    """Compute the exponential backoff delay before a given retry attempt.

    `attempt` is 1-indexed and refers to the attempt that just failed; the
    returned delay is how long to wait before the next attempt.
    """
    if attempt < 1:
        raise ValueError("attempt must be a positive integer")
    delay = retry.initial_delay_seconds * (retry.backoff ** (attempt - 1))
    return min(delay, retry.maximum_delay_seconds)
