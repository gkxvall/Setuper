"""Tests for pure retry backoff and attempt-count calculations."""

import pytest

from setuper.domain.models import RetrySpec
from setuper.domain.policies import compute_retry_delay, total_attempts


def test_total_attempts_without_retry_policy_is_one() -> None:
    """No retry policy means exactly one attempt."""
    assert total_attempts(None) == 1


def test_total_attempts_uses_declared_attempts() -> None:
    """A retry policy's attempts field is returned directly."""
    retry = RetrySpec(
        attempts=5,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=10.0,
        backoff=2.0,
    )

    assert total_attempts(retry) == 5


def test_compute_retry_delay_grows_exponentially() -> None:
    """Each subsequent attempt's delay grows by the backoff multiplier."""
    retry = RetrySpec(
        attempts=5,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=100.0,
        backoff=2.0,
    )

    assert compute_retry_delay(retry, 1) == 1.0
    assert compute_retry_delay(retry, 2) == 2.0
    assert compute_retry_delay(retry, 3) == 4.0
    assert compute_retry_delay(retry, 4) == 8.0


def test_compute_retry_delay_caps_at_maximum_delay() -> None:
    """Delay growth is capped at the declared maximum."""
    retry = RetrySpec(
        attempts=10,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=5.0,
        backoff=2.0,
    )

    assert compute_retry_delay(retry, 10) == 5.0


def test_compute_retry_delay_rejects_non_positive_attempt() -> None:
    """An attempt index below 1 is not a valid retry attempt number."""
    retry = RetrySpec(
        attempts=3,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=10.0,
        backoff=2.0,
    )

    with pytest.raises(ValueError, match="positive"):
        compute_retry_delay(retry, 0)
