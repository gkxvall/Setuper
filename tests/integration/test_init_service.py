"""Integration tests for project initialization."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from setuper.application.setup_service import SetupService
from setuper.domain.enums import SetupSource
from setuper.domain.errors import ManifestIOError, ManifestValidationError
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.hashing import hash_manifest
from setuper.infrastructure.manifests import load_manifest
from setuper.infrastructure.migrations import MIGRATIONS
from setuper.infrastructure.setup_repository import SetupRepository

SETUP_ID = UUID("e84b8d08-e05d-49de-a7ab-4e38f919eb89")
NOW = datetime(2026, 7, 29, 12, tzinfo=UTC)


def make_service(tmp_path: Path) -> tuple[SetupService, SetupRepository]:
    """Create an initialized deterministic setup service."""
    connection = connect_database(tmp_path / "state.db")
    run_migrations(connection, MIGRATIONS)
    repository = SetupRepository(connection)
    return (
        SetupService(
            repository,
            id_factory=lambda: SETUP_ID,
            clock=lambda: NOW,
        ),
        repository,
    )


def test_init_creates_hashes_and_registers_project_manifest(tmp_path: Path) -> None:
    """Initialization creates one stable, untrusted project setup."""
    project = tmp_path / "Projet Démo"
    project.mkdir()
    service, repository = make_service(tmp_path)

    result = service.init_project(project)

    assert result.manifest_path == project / ".setuper.yaml"
    assert load_manifest(result.manifest_path) == result.manifest
    assert result.manifest.id == SETUP_ID
    record = repository.get_by_name("Projet Démo")
    assert record.source is SetupSource.PROJECT
    assert record.manifest_hash == hash_manifest(result.manifest_path)


def test_init_refuses_to_overwrite_existing_file_or_symlink(tmp_path: Path) -> None:
    """Existing project manifests and broken symlinks remain untouched."""
    project = tmp_path / "workspace"
    project.mkdir()
    manifest_path = project / ".setuper.yaml"
    manifest_path.write_text("existing\n", encoding="utf-8")
    service, _ = make_service(tmp_path)

    with pytest.raises(ManifestValidationError):
        service.init_project(project)
    assert manifest_path.read_text(encoding="utf-8") == "existing\n"

    manifest_path.unlink()
    manifest_path.symlink_to(project / "missing-target")
    with pytest.raises(ManifestValidationError):
        service.init_project(project)
    assert manifest_path.is_symlink()


def test_init_rejects_missing_or_nondirectory_paths(tmp_path: Path) -> None:
    """Invalid project paths return typed actionable failures."""
    service, _ = make_service(tmp_path)
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ManifestIOError):
        service.init_project(tmp_path / "missing")
    with pytest.raises(ManifestValidationError):
        service.init_project(file_path)
