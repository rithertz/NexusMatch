
"""Apply PostgreSQL schema migrations in order."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "sql" / "schema"

# Stable, application-specific PostgreSQL advisory lock key.
LOCK_KEY = 7812042601


def load_settings():
    """Load the existing application database configuration."""
    sys.path.insert(0, str(BACKEND_DIR))

    from app.core.config import settings

    return settings


def database_dsn() -> str:
    """Build the connection string from application settings."""
    settings = load_settings()

    return make_conninfo(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def discover_migrations() -> list[Path]:
    """Discover numbered SQL migrations in deterministic order."""
    migrations = sorted(MIGRATIONS_DIR.glob("[0-9]*_*.sql"))

    if not migrations:
        raise RuntimeError(
            f"No migrations found in {MIGRATIONS_DIR}"
        )

    versions = [
        path.name.split("_", maxsplit=1)[0]
        for path in migrations
    ]

    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version numbers found")

    return migrations


def migration_checksum(path: Path) -> str:
    """Calculate the SHA-256 checksum of the original migration file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migration_body(path: Path) -> str:
    """Remove exactly one standalone outer transaction wrapper."""
    content = path.read_text(encoding="utf-8-sig")

    content, begin_count = re.subn(
        r"(?im)^\s*BEGIN;\s*$",
        "",
        content,
        count=1,
    )

    content, commit_count = re.subn(
        r"(?im)^\s*COMMIT;\s*$",
        "",
        content,
        count=1,
    )

    if begin_count != 1 or commit_count != 1:
        raise RuntimeError(
            f"{path.name} must contain one standalone BEGIN; "
            "and one standalone COMMIT; transaction wrapper"
        )

    return content


def ensure_history_table(connection: psycopg.Connection) -> None:
    """Create the migration history table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def apply_migrations(*, baseline_existing: bool = False) -> None:
    """Apply pending migrations and verify previously applied checksums."""
    migrations = discover_migrations()

    with psycopg.connect(database_dsn(), autocommit=True) as connection:
        # Hold a session-level lock on the same connection used for
        # migration execution and history updates.
        connection.execute(
            "SELECT pg_advisory_lock(%s)",
            (LOCK_KEY,),
        )

        try:
            ensure_history_table(connection)

            recorded = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    """
                    SELECT version, filename, checksum
                    FROM schema_migrations
                    """
                ).fetchall()
            }

            if baseline_existing and not recorded:
                print(
                    "WARNING: recording migration history without "
                    "executing SQL. Verify the existing schema first."
                )

                with connection.transaction():
                    for path in migrations:
                        version = path.name.split("_", maxsplit=1)[0]

                        connection.execute(
                            """
                            INSERT INTO schema_migrations
                                (version, filename, checksum)
                            VALUES (%s, %s, %s)
                            """,
                            (
                                version,
                                path.name,
                                migration_checksum(path),
                            ),
                        )

                print(f"Recorded {len(migrations)} migration versions.")
                return

            applied_count = 0

            for path in migrations:
                version = path.name.split("_", maxsplit=1)[0]
                checksum = migration_checksum(path)

                if version in recorded:
                    filename, previous_checksum = recorded[version]

                    if (
                        filename != path.name
                        or previous_checksum != checksum
                    ):
                        raise RuntimeError(
                            f"Applied migration {version} differs from "
                            "its recorded filename or checksum. "
                            "Add a new migration instead of editing "
                            "an applied migration."
                        )

                    print(f"Already applied: {path.name}")
                    continue

                body = migration_body(path)
                print(f"Applying: {path.name}")

                # Psycopg's simple-query protocol supports multiple SQL
                # statements when prepare=False. The schema changes and
                # history insert share this transaction.
                with connection.transaction():
                    connection.execute(body, prepare=False)

                    connection.execute(
                        """
                        INSERT INTO schema_migrations
                            (version, filename, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (version, path.name, checksum),
                    )

                recorded[version] = (path.name, checksum)
                applied_count += 1

                print(f"Applied: {path.name}")

            print(
                "Migration run complete; "
                f"applied {applied_count} migration(s)."
            )

        finally:
            connection.execute(
                "SELECT pg_advisory_unlock(%s)",
                (LOCK_KEY,),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--baseline-existing",
        action="store_true",
        help=(
            "Record migration versions without executing SQL. "
            "Use only after independently verifying the complete schema."
        ),
    )

    args = parser.parse_args()

    try:
        apply_migrations(baseline_existing=args.baseline_existing)
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
