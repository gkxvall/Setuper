"""Tests for platform-standard Setuper paths."""

from pathlib import Path

import pytest

from setuper.domain.enums import ExitCode
from setuper.domain.errors import (
    ManifestIOError,
    PermissionDeniedError,
    UnsupportedPlatformError,
)
from setuper.infrastructure.paths import resolve_paths


def test_macos_paths_match_documented_locations(tmp_path: Path) -> None:
    """macOS data, logs, cache, manifests, and database paths are stable."""
    home = tmp_path / "Méd Vall"
    paths = resolve_paths(home=home, platform_name="darwin")

    data_directory = home / "Library" / "Application Support" / "setuper"
    assert paths.data_directory == data_directory
    assert paths.manifest_directory == data_directory / "setups"
    assert paths.plugin_directory == data_directory / "plugins"
    assert paths.database_path == data_directory / "state.db"
    assert paths.config_path == data_directory / "config.yaml"
    assert paths.log_directory == home / "Library" / "Logs" / "setuper"
    assert paths.cache_directory == home / "Library" / "Caches" / "setuper"


def test_ensure_directories_creates_each_private_location(tmp_path: Path) -> None:
    """Directory creation covers every mutable user-data category."""
    paths = resolve_paths(home=tmp_path, platform_name="darwin")

    paths.ensure_directories()

    assert paths.data_directory.is_dir()
    assert paths.manifest_directory.is_dir()
    assert paths.plugin_directory.is_dir()
    assert paths.log_directory.is_dir()
    assert paths.cache_directory.is_dir()


def test_unsupported_platform_fails_honestly(tmp_path: Path) -> None:
    """Non-macOS operation returns the documented unsupported exit class."""
    with pytest.raises(UnsupportedPlatformError) as raised:
        resolve_paths(home=tmp_path, platform_name="linux")

    assert raised.value.exit_code is ExitCode.UNSUPPORTED
    assert raised.value.details == {"platform": "linux"}


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (PermissionError("denied"), PermissionDeniedError),
        (OSError("disk unavailable"), ManifestIOError),
    ],
)
def test_directory_creation_failures_are_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: OSError,
    expected_error: type[Exception],
) -> None:
    """User-state filesystem failures never escape as raw exceptions."""
    paths = resolve_paths(home=tmp_path, platform_name="darwin")

    def fail_mkdir(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(expected_error):
        paths.ensure_directories()
