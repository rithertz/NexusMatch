"""Unit tests for fail-closed test database selection."""

import pytest
from psycopg.conninfo import make_conninfo
from scripts.verify_test_database import verify_test_database


@pytest.mark.parametrize(
    "database_name",
    [
        "nexusmatch",
        "nexusmatch_m5_test_20261013",
        "nexusmatch_ci_local_test_20261013",
        "nexusmatch_ci_test",
        "some_other_database",
    ],
)
def test_rejects_unapproved_or_protected_database_before_connecting(database_name):
    dsn = make_conninfo(
        host="localhost",
        port=5432,
        dbname=database_name,
        user="nexusmatch",
    )

    with pytest.raises(RuntimeError, match="not allowlisted"):
        verify_test_database(dsn)
