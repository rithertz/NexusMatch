"""PostgreSQL connection dependency for API endpoints."""

import psycopg
from app.core.config import settings
from psycopg.rows import dict_row


def get_db():
    """Yield a dictionary-row PostgreSQL connection per request."""
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        connect_timeout=5,
        row_factory=dict_row,
    ) as connection:
        yield connection