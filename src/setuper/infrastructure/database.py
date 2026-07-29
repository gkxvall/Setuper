"""SQLite connection policy and transactional migration runner."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from setuper.domain.errors import DatabaseError, DatabaseMigrationError

SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable, ordered SQLite schema migration."""

    version: int
    description: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject invalid migration metadata at definition time."""
        if self.version < 1:
            raise ValueError("migration version must be positive")
        if not self.description.strip():
            raise ValueError("migration description must not be empty")
        if not self.statements:
            raise ValueError("migration must contain at least one statement")


def connect_database(path: Path) -> sqlite3.Connection:
    """Open SQLite state with Setuper's required safety pragmas."""
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
    except (OSError, sqlite3.Error) as error:
        raise DatabaseError(
            f"Could not open Setuper database: {path}",
            details={"path": str(path)},
        ) from error


def run_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration],
) -> None:
    """Apply each pending migration once in its own transaction."""
    _validate_migration_order(migrations)
    try:
        connection.execute(SCHEMA_MIGRATIONS_SQL)
        connection.commit()
        applied_versions = {
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        }
    except sqlite3.Error as error:
        raise DatabaseMigrationError(
            "Could not initialize database migration state"
        ) from error

    for migration in migrations:
        if migration.version in applied_versions:
            continue
        _apply_migration(connection, migration)


def _validate_migration_order(migrations: Sequence[Migration]) -> None:
    """Require unique, strictly increasing migration versions."""
    versions = [migration.version for migration in migrations]
    if versions != sorted(set(versions)):
        raise ValueError("migrations must have unique, increasing versions")


def _apply_migration(
    connection: sqlite3.Connection,
    migration: Migration,
) -> None:
    """Apply one migration and its history row atomically."""
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (migration.version, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    except sqlite3.Error as error:
        connection.rollback()
        raise DatabaseMigrationError(
            f"Database migration {migration.version} failed",
            details={
                "version": migration.version,
                "description": migration.description,
            },
        ) from error
