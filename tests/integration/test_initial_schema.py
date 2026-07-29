"""Integration tests for the first operational-state migration."""

import sqlite3
from pathlib import Path

import pytest

from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.migrations import MIGRATIONS

EXPECTED_TABLES = {
    "schema_migrations",
    "setups",
    "trust_approvals",
    "launches",
    "resource_runs",
    "launch_events",
    "capture_history",
}

EXPECTED_INDEXES = {
    "idx_launches_setup_started",
    "idx_resource_runs_launch_resource",
    "idx_launch_events_launch_created",
    "idx_trust_approvals_setup_hash",
}


def test_initial_migration_creates_documented_tables_and_indexes(
    tmp_path: Path,
) -> None:
    """Migration 1 creates every documented table and lookup index."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
            )
        }
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

    assert tables == EXPECTED_TABLES
    assert indexes >= EXPECTED_INDEXES
    assert versions == [1]


@pytest.mark.parametrize(
    ("table", "column", "invalid_value"),
    [
        ("setups", "source", "remote"),
        ("launches", "status", "unknown"),
        ("resource_runs", "status", "unknown"),
        ("capture_history", "command", "delete"),
    ],
)
def test_initial_schema_rejects_invalid_enum_values(
    tmp_path: Path,
    table: str,
    column: str,
    invalid_value: str,
) -> None:
    """Persisted enum-like fields cannot drift from domain values."""
    with connect_database(tmp_path / f"{table}.db") as connection:
        run_migrations(connection, MIGRATIONS)
        _insert_required_parents(connection)
        statement, parameters = _invalid_insert(table, column, invalid_value)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, parameters)


def test_foreign_keys_apply_documented_delete_behavior(tmp_path: Path) -> None:
    """Setup deletion cascades runtime state and detaches capture history."""
    with connect_database(tmp_path / "state.db") as connection:
        run_migrations(connection, MIGRATIONS)
        _insert_required_parents(connection)
        connection.execute(
            """
            INSERT INTO capture_history(
                id, setup_id, command, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "capture-1",
                "setup-1",
                "inspect",
                "{}",
                "2026-07-29T00:00:00+00:00",
            ),
        )
        connection.execute("DELETE FROM setups WHERE id = 'setup-1'")

        assert connection.execute("SELECT COUNT(*) FROM launches").fetchone()[0] == 0
        capture_setup_id = connection.execute(
            "SELECT setup_id FROM capture_history WHERE id = 'capture-1'"
        ).fetchone()[0]

    assert capture_setup_id is None


def _insert_required_parents(connection: sqlite3.Connection) -> None:
    """Insert stable parent rows used by schema constraint tests."""
    connection.execute(
        """
        INSERT INTO setups(
            id, name, manifest_path, manifest_hash, source, created_at, updated_at
        ) VALUES (
            'setup-1', 'workspace', '/tmp/workspace.yaml', 'hash', 'local',
            '2026-07-29T00:00:00+00:00', '2026-07-29T00:00:00+00:00'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO launches(
            id, setup_id, manifest_hash, status, started_at, initiated_by
        ) VALUES (
            'launch-1', 'setup-1', 'hash', 'starting',
            '2026-07-29T00:00:00+00:00', 'cli'
        )
        """
    )


def _invalid_insert(
    table: str,
    column: str,
    invalid_value: str,
) -> tuple[str, tuple[str, ...]]:
    """Return a complete insert targeting one invalid constrained value."""
    if table == "setups":
        return (
            """
            INSERT INTO setups(
                id, name, manifest_path, manifest_hash, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "setup-invalid",
                "invalid",
                "/tmp/invalid.yaml",
                "hash",
                invalid_value,
                "2026-07-29T00:00:00+00:00",
                "2026-07-29T00:00:00+00:00",
            ),
        )
    if table == "launches":
        return (
            """
            INSERT INTO launches(
                id, setup_id, manifest_hash, status, started_at, initiated_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "launch-invalid",
                "setup-1",
                "hash",
                invalid_value,
                "2026-07-29T00:00:00+00:00",
                "cli",
            ),
        )
    if table == "resource_runs":
        return (
            """
            INSERT INTO resource_runs(
                id, launch_id, resource_id, resource_type, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("run-invalid", "launch-1", "resource", "command", invalid_value),
        )
    if table == "capture_history":
        return (
            """
            INSERT INTO capture_history(
                id, setup_id, command, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "capture-invalid",
                "setup-1",
                invalid_value,
                "{}",
                "2026-07-29T00:00:00+00:00",
            ),
        )
    raise AssertionError(f"unsupported test table: {table}.{column}")
