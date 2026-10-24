"""Test configuration to keep project imports stable from the repository root."""

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.verify_test_database import verify_test_database


@pytest.fixture(scope="session", autouse=True)
def verify_test_database_identity():
    dsn = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not dsn:
        return

    try:
        verify_test_database(dsn)
    except (RuntimeError, ValueError) as exc:
        pytest.exit(
            f"Refusing database tests: {exc}",
            returncode=2,
        )
