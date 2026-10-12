
"""Unit tests for PostgreSQL migration discovery and parsing."""

from pathlib import Path

import pytest

from backend.scripts.migrate import (
    discover_migrations,
    migration_body,
    migration_checksum,
)


def test_migrations_are_discovered_in_numeric_order():
    migrations = discover_migrations()

    assert [path.name for path in migrations] == [
        "001_initial_schema.sql",
        "002_registration_capacity.sql",
        "003_tournament_capacity_updates.sql",
        "004_registration_status_capacity.sql",
    ]


@pytest.mark.parametrize(
    "filename",
    [
        "001_initial_schema.sql",
        "002_registration_capacity.sql",
        "003_tournament_capacity_updates.sql",
        "004_registration_status_capacity.sql",
    ],
)
def test_migration_body_removes_outer_transaction(filename):
    paths = {path.name: path for path in discover_migrations()}

    body = migration_body(paths[filename])
    lines = [line.strip().upper() for line in body.splitlines()]

    assert "BEGIN;" not in lines
    assert "COMMIT;" not in lines
    assert body.strip()


def test_checksum_is_deterministic(tmp_path: Path):
    migration = tmp_path / "005_example.sql"
    migration.write_text("SELECT 1;\n", encoding="utf-8")

    assert migration_checksum(migration) == migration_checksum(migration)
    assert len(migration_checksum(migration)) == 64


def test_migration_without_transaction_wrapper_is_rejected(tmp_path: Path):
    migration = tmp_path / "005_invalid.sql"
    migration.write_text(
        "CREATE TABLE example (id INT);\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="standalone BEGIN"):
        migration_body(migration)
