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
CLONE_ID = UUID("8242489f-4611-4870-8cf5-13aecafd62e6")
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


def test_edit_validates_before_atomically_replacing_manifest(tmp_path: Path) -> None:
    """A valid edit commits while an identity change preserves the prior file."""
    project = tmp_path / "workspace"
    project.mkdir()
    service, repository = make_service(tmp_path)
    initialized = service.init_project(project)

    def add_description(path: Path) -> None:
        path.write_text(
            path.read_text(encoding="utf-8") + "description: Edited safely\n",
            encoding="utf-8",
        )

    result = service.edit_setup("workspace", add_description)

    assert result.manifest.description == "Edited safely"
    assert repository.get_by_name("workspace").manifest_hash == hash_manifest(
        initialized.manifest_path
    )

    contents = initialized.manifest_path.read_text(encoding="utf-8")

    def change_name(path: Path) -> None:
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "name: workspace",
                "name: changed",
            ),
            encoding="utf-8",
        )

    with pytest.raises(ManifestValidationError):
        service.edit_setup("workspace", change_name)
    assert initialized.manifest_path.read_text(encoding="utf-8") == contents
    assert not list(project.glob(".*.edit.*.yaml"))


def test_clone_creates_new_local_identity_without_overwriting(tmp_path: Path) -> None:
    """Clones preserve content but receive independent metadata and storage."""
    project = tmp_path / "source"
    project.mkdir()
    service, repository = make_service(tmp_path)
    source = service.init_project(project)
    clone_service = SetupService(
        repository,
        id_factory=lambda: CLONE_ID,
        clock=lambda: NOW,
    )
    manifest_directory = tmp_path / "managed setups"

    result = clone_service.clone_setup("source", "target copy", manifest_directory)

    assert result.manifest.name == "target copy"
    assert result.manifest.id == CLONE_ID
    assert result.manifest.id != source.manifest.id
    assert result.manifest_path.parent == manifest_directory.resolve()
    assert result.manifest_path.name == f"{result.manifest.id}.yaml"
    record = repository.get_by_name("target copy")
    assert record.source is SetupSource.LOCAL
    assert record.manifest_hash == hash_manifest(result.manifest_path)

    with pytest.raises(ManifestValidationError):
        clone_service.clone_setup("source", "target copy", manifest_directory)
    assert len(list(manifest_directory.glob("*.yaml"))) == 1


def test_rename_updates_manifest_and_metadata_but_preserves_identity(
    tmp_path: Path,
) -> None:
    """Rename retains the UUID and path while changing the hash and lookup name."""
    project = tmp_path / "source"
    project.mkdir()
    service, repository = make_service(tmp_path)
    initialized = service.init_project(project)
    original_hash = repository.get_by_name("source").manifest_hash

    result = service.rename_setup("source", "  Démo renamed  ")

    assert result.manifest.name == "Démo renamed"
    assert result.manifest.id == initialized.manifest.id
    assert result.manifest_path == initialized.manifest_path
    record = repository.get_by_name("Démo renamed")
    assert record.manifest_hash != original_hash
    assert record.manifest_hash == hash_manifest(result.manifest_path)


def test_rename_refuses_existing_target_without_changing_source(
    tmp_path: Path,
) -> None:
    """A duplicate target name leaves both setup manifests untouched."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    service, _ = make_service(tmp_path)
    original = service.init_project(first)
    second_connection = connect_database(tmp_path / "state.db")
    second_service = SetupService(
        SetupRepository(second_connection),
        id_factory=lambda: CLONE_ID,
        clock=lambda: NOW,
    )
    second_service.init_project(second)
    contents = original.manifest_path.read_text(encoding="utf-8")

    with pytest.raises(ManifestValidationError):
        service.rename_setup("first", "second")

    assert original.manifest_path.read_text(encoding="utf-8") == contents
