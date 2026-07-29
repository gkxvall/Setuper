"""Tests for exact manifest revision hashes."""

import hashlib
from pathlib import Path

import pytest

from setuper.domain.errors import ManifestIOError
from setuper.infrastructure.hashing import hash_manifest


def test_manifest_hash_matches_sha256_bytes(tmp_path: Path) -> None:
    """Hashing uses exact UTF-8 file bytes and lowercase SHA-256."""
    manifest_path = tmp_path / "développement.yaml"
    contents = "schema_version: 1\nname: développement\n"
    manifest_path.write_text(contents, encoding="utf-8")

    assert hash_manifest(manifest_path) == hashlib.sha256(contents.encode()).hexdigest()


def test_semantic_whitespace_change_invalidates_hash(tmp_path: Path) -> None:
    """Any exact-file modification produces a different trust revision."""
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text("name: workspace\n", encoding="utf-8")
    original = hash_manifest(manifest_path)

    manifest_path.write_text("name:  workspace\n", encoding="utf-8")

    assert hash_manifest(manifest_path) != original


def test_missing_manifest_hash_is_a_typed_io_error(tmp_path: Path) -> None:
    """Hash filesystem failures do not expose raw exceptions."""
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(ManifestIOError) as raised:
        hash_manifest(missing_path)

    assert raised.value.details == {"path": str(missing_path)}
