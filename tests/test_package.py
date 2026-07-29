"""Smoke tests for the top-level package."""

import setuper


def test_package_is_importable() -> None:
    """The source-layout package can be imported by its public name."""
    assert setuper.__name__ == "setuper"
