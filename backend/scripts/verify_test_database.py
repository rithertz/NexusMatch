"""Verify an allowlisted local test database before migrations or tests."""

from __future__ import annotations

import argparse
import os

import psycopg
from psycopg.conninfo import conninfo_to_dict

ALLOWED_TEST_DATABASES = {
    "nexusmatch_ci_isolated_test": {"nexusmatch_ci": {5432}},
    "nexusmatch_e2e_test": {"nexusmatch_e2e": {5432, 5433}},
}
PROTECTED_DATABASES = {
    "nexusmatch",
    "nexusmatch_m5_test_20261013",
    "nexusmatch_ci_local_test_20261013",
    "nexusmatch_ci_test",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def verify_test_database(dsn: str, *, require_empty: bool = False) -> None:
    configured = conninfo_to_dict(dsn)
    database_name = configured.get("dbname")
    if (
        database_name in PROTECTED_DATABASES
        or database_name not in ALLOWED_TEST_DATABASES
    ):
        raise RuntimeError(
            "Refusing database operation: target name is not allowlisted."
        )

    host = configured.get("host", "localhost")
    configured_port = int(configured.get("port", "5432"))
    if host not in LOCAL_HOSTS:
        raise RuntimeError(
            "Refusing database operation: target must be a local service."
        )

    allowed_users = ALLOWED_TEST_DATABASES[database_name]
    allowed_ports = allowed_users.get(configured.get("user", ""))
    if allowed_ports is None or configured_port not in allowed_ports:
        raise RuntimeError(
            "Refusing database operation: configured user or port is not "
            "approved for this test database."
        )

    try:
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            actual_name, actual_user, server_port = connection.execute(
                "SELECT current_database(), current_user, inet_server_port()"
            ).fetchone()
            if (
                actual_name != database_name
                or actual_name in PROTECTED_DATABASES
                or actual_user != configured.get("user")
                or server_port != 5432
            ):
                raise RuntimeError(
                    "Refusing database operation: connected database identity "
                    "does not match the allowlisted target."
                )

            if require_empty:
                table_count = connection.execute(
                    """
                    SELECT count(*)
                    FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                    """
                ).fetchone()[0]
                if table_count:
                    raise RuntimeError(
                        "Refusing database operation: test database is not empty."
                    )
    except psycopg.Error:
        raise RuntimeError(
            "Refusing database operation: target identity could not be verified."
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-empty",
        action="store_true",
        help="Also require that the public schema contains no tables.",
    )
    args = parser.parse_args()

    dsn = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "NEXUSMATCH_TEST_DATABASE_URL is required; refusing database operation."
        )
    try:
        verify_test_database(dsn, require_empty=args.require_empty)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print("Verified allowlisted test database identity.")


if __name__ == "__main__":
    main()
