"""Application service for setup lifecycle operations."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from setuper.domain.enums import Platform, SetupSource
from setuper.domain.errors import (
    DatabaseError,
    ManifestIOError,
    ManifestValidationError,
)
from setuper.domain.models import SetupManifest
from setuper.infrastructure.hashing import hash_manifest
from setuper.infrastructure.manifests import save_manifest
from setuper.infrastructure.setup_repository import SetupRecord, SetupRepository

PROJECT_MANIFEST_NAME = ".setuper.yaml"


@dataclass(frozen=True, slots=True)
class InitResult:
    """Result of initializing one project-local setup."""

    manifest: SetupManifest
    manifest_path: Path


class SetupService:
    """Coordinate setup manifests and their operational metadata."""

    def __init__(
        self,
        repository: SetupRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Create a setup service with injectable identity and time sources."""
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or _utc_now

    def init_project(self, project_path: Path) -> InitResult:
        """Create and register a new project-local manifest."""
        try:
            resolved_project = project_path.expanduser().resolve(strict=True)
        except OSError as error:
            raise ManifestIOError(
                f"Project path does not exist: {project_path}",
                details={"path": str(project_path)},
            ) from error
        if not resolved_project.is_dir():
            raise ManifestValidationError(
                f"Project path is not a directory: {resolved_project}",
                details={"path": str(resolved_project)},
            )
        if not resolved_project.name:
            raise ManifestValidationError(
                "Cannot derive a setup name from the filesystem root",
                details={"path": str(resolved_project)},
            )

        manifest_path = resolved_project / PROJECT_MANIFEST_NAME
        if os.path.lexists(manifest_path):
            raise ManifestValidationError(
                f"Project manifest already exists: {manifest_path}",
                details={"path": str(manifest_path)},
            )

        setup_id = self._id_factory()
        manifest = SetupManifest(
            id=setup_id,
            name=resolved_project.name,
            platforms=(Platform.MACOS,),
        )
        save_manifest(manifest_path, manifest)
        timestamp = self._clock()
        record = SetupRecord(
            id=setup_id,
            name=manifest.name,
            manifest_path=manifest_path,
            manifest_hash=hash_manifest(manifest_path),
            source=SetupSource.PROJECT,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self._repository.create(record)
        except DatabaseError as error:
            raise DatabaseError(
                f"Manifest created but registration failed: {manifest_path}",
                details={"path": str(manifest_path), "name": manifest.name},
            ) from error
        return InitResult(manifest=manifest, manifest_path=manifest_path)

    def list_setups(self) -> tuple[SetupRecord, ...]:
        """Return stored setups in stable name order."""
        return self._repository.list()


def _utc_now() -> datetime:
    """Return the current aware UTC time."""
    return datetime.now(UTC)
