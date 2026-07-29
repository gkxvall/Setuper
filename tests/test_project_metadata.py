"""Tests for the package metadata."""

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def test_project_targets_supported_python() -> None:
    """Package metadata declares the documented project and Python baseline."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["name"] == "setuper"
    assert project["version"] == "0.1.0"
    assert project["readme"] == "README.md"
    assert project["license"] == "MIT"
    assert project["requires-python"] == ">=3.12"
