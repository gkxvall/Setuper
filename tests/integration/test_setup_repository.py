"""Integration tests for setup metadata persistence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from setuper.domain.enums import SetupSource
from setuper.domain.errors import DatabaseError, SetupNotFoundError
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.migrations import MIGRATIONS
from setuper.infrastructure.setup_repository import SetupRecord, SetupRepository

SETUP_ID = UUID("a6f16d84-1450-407c-9c59-cbca28bf95fc")
CREATED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)


def make_record(tmp_path: Path, *, name: str = "développement") -> SetupRecord:
    """Create deterministic setup metadata."""
    return SetupRecord(
        id=SETUP_ID,
        name=name,
        manifest_path=(tmp_path / "Setups With Spaces" / f"{name}.yaml").absolute(),
        manifest_hash="a" * 64,
        source=SetupSource.LOCAL,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def test_create_get_and_list_setups(tmp_path: Path) -> None:
    """Unicode names and paths with spaces round-trip in stable order."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        repository = SetupRepository(connection)
        development = make_record(tmp_path)
        alpha = replace(
            make_record(tmp_path, name="alpha"),
            id=UUID("59bb4458-ae21-4bf7-8d46-c002282a3f18"),
        )

        repository.create(development)
        repository.create(alpha)

        assert repository.get_by_name("développement") == development
        assert repository.list() == (alpha, development)


def test_update_and_delete_setup(tmp_path: Path) -> None:
    """Updates preserve identity and deletion returns the removed row."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        repository = SetupRepository(connection)
        original = make_record(tmp_path)
        updated = replace(
            original,
            name="renamed",
            manifest_hash="b" * 64,
            source=SetupSource.IMPORTED,
            updated_at=CREATED_AT + timedelta(minutes=1),
        )
        repository.create(original)

        repository.update(updated)

        assert repository.get_by_name("renamed") == updated
        assert repository.delete("renamed") == updated
        assert repository.list() == ()


def test_missing_setup_operations_are_typed(tmp_path: Path) -> None:
    """Missing reads, updates, and deletes return SetupNotFoundError."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        repository = SetupRepository(connection)
        missing = make_record(tmp_path)

        with pytest.raises(SetupNotFoundError):
            repository.get_by_name("missing")
        with pytest.raises(SetupNotFoundError):
            repository.update(missing)
        with pytest.raises(SetupNotFoundError):
            repository.delete("missing")


def test_duplicate_setup_name_is_a_redacted_database_error(tmp_path: Path) -> None:
    """Unique-name conflicts do not leak raw SQLite diagnostics."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        repository = SetupRepository(connection)
        repository.create(make_record(tmp_path))

        duplicate = replace(
            make_record(tmp_path),
            id=UUID("8c92cdcf-b50e-4326-8130-f5c16e108365"),
            manifest_path=tmp_path / "other.yaml",
        )
        with pytest.raises(DatabaseError) as raised:
            repository.create(duplicate)

    assert raised.value.details == {"name": "développement"}
    assert "UNIQUE" not in str(raised.value)


def test_naive_timestamps_are_rejected_before_insert(tmp_path: Path) -> None:
    """Repositories never write ambiguous local timestamps."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        repository = SetupRepository(connection)
        record = replace(make_record(tmp_path), created_at=datetime(2026, 7, 29))

        with pytest.raises(ValueError, match="timezone-aware"):
            repository.create(record)
