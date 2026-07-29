"""Integration tests for SQLite connection and migrations."""

from pathlib import Path

import pytest

from setuper.domain.errors import DatabaseMigrationError
from setuper.infrastructure.database import (
    Migration,
    connect_database,
    run_migrations,
)


def test_connection_enables_required_sqlite_pragmas(tmp_path: Path) -> None:
    """Connections create parent paths and enable foreign keys and WAL."""
    database_path = tmp_path / "Application Support" / "setuper" / "state.db"

    with connect_database(database_path) as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert database_path.is_file()
    assert foreign_keys == 1
    assert journal_mode == "wal"
    assert busy_timeout == 5000


def test_migrations_apply_in_order_and_are_idempotent(tmp_path: Path) -> None:
    """Pending migrations and history rows are applied exactly once."""
    migrations = (
        Migration(
            version=1,
            description="create example",
            statements=("CREATE TABLE example (id INTEGER PRIMARY KEY)",),
        ),
        Migration(
            version=2,
            description="add example name",
            statements=("ALTER TABLE example ADD COLUMN name TEXT",),
        ),
    )

    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, migrations)
        run_migrations(connection, migrations)
        columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(example)")
        ]
        history = connection.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert columns == ["id", "name"]
    assert [row["version"] for row in history] == [1, 2]
    assert all(row["applied_at"].endswith("+00:00") for row in history)


def test_failed_migration_is_rolled_back(tmp_path: Path) -> None:
    """DDL and history remain unchanged when any statement fails."""
    migration = Migration(
        version=1,
        description="fail after table creation",
        statements=(
            "CREATE TABLE transient_table (id INTEGER PRIMARY KEY)",
            "INVALID SQL",
        ),
    )

    with connect_database(tmp_path / "state.db") as connection:
        with pytest.raises(DatabaseMigrationError) as raised:
            run_migrations(connection, (migration,))
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        history = connection.execute("SELECT version FROM schema_migrations").fetchall()

    assert raised.value.details["version"] == 1
    assert "transient_table" not in tables
    assert history == []


@pytest.mark.parametrize(
    "migrations",
    [
        (
            Migration(2, "second", ("SELECT 1",)),
            Migration(1, "first", ("SELECT 1",)),
        ),
        (
            Migration(1, "first", ("SELECT 1",)),
            Migration(1, "duplicate", ("SELECT 1",)),
        ),
    ],
)
def test_migration_order_must_be_unique_and_increasing(
    tmp_path: Path,
    migrations: tuple[Migration, ...],
) -> None:
    """Ambiguous migration sequences are rejected before database mutation."""
    with (
        connect_database(tmp_path / "state.db") as connection,
        pytest.raises(ValueError, match="unique, increasing"),
    ):
        run_migrations(connection, migrations)


def test_migration_definition_rejects_invalid_metadata() -> None:
    """Migration objects require positive versions, descriptions, and SQL."""
    with pytest.raises(ValueError, match="positive"):
        Migration(0, "invalid", ("SELECT 1",))
    with pytest.raises(ValueError, match="description"):
        Migration(1, " ", ("SELECT 1",))
    with pytest.raises(ValueError, match="statement"):
        Migration(1, "empty", ())
