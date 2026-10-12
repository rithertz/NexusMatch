"""Player profile endpoints."""

from collections.abc import Generator
from typing import Annotated

import psycopg
from app.db.connection import get_db
from app.schemas.player import PlayerCreate, PlayerResponse, PlayerUpdate
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.errors import UniqueViolation

router = APIRouter(prefix="/api/v1/players", tags=["Players"])

DbConnection = Annotated[
    Generator[psycopg.Connection, None, None],
    Depends(get_db),
]

_COLUMNS = "player_id, username, display_name, email, created_at"


def _player_or_404(connection: psycopg.Connection, player_id: int):
    row = connection.execute(
        f"SELECT {_COLUMNS} FROM players WHERE player_id = %s",
        (player_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found.",
        )
    return row


def _database_error(exc: psycopg.Error) -> HTTPException:
    if isinstance(exc, UniqueViolation):
        detail = "A player with this username or email already exists."
        message = str(exc).lower()
        if "username" in message:
            detail = "A player with this username already exists."
        elif "email" in message:
            detail = "A player with this email already exists."
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The player could not be saved.",
    )


@router.post(
    "",
    response_model=PlayerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_player(payload: PlayerCreate, connection: DbConnection):
    try:
        with connection.transaction():
            row = connection.execute(
                """
                INSERT INTO players (username, display_name, email)
                VALUES (%s, %s, %s)
                RETURNING player_id, username, display_name, email, created_at
                """,
                (
                    payload.username.strip(),
                    payload.display_name.strip(),
                    payload.email,
                ),
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row


@router.get("", response_model=list[PlayerResponse])
def list_players(
    connection: DbConnection,
    username: str | None = Query(default=None, min_length=1, max_length=40),
    display_name: str | None = Query(default=None, min_length=1, max_length=100),
    email: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions: list[str] = []
    parameters: list[object] = []

    if username is not None:
        conditions.append("LOWER(username) = LOWER(%s)")
        parameters.append(username.strip())
    if display_name is not None:
        conditions.append("LOWER(display_name) = LOWER(%s)")
        parameters.append(display_name.strip())
    if email is not None:
        conditions.append("LOWER(email) = LOWER(%s)")
        parameters.append(email.strip())

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    parameters.extend([limit, offset])

    return connection.execute(
        f"""
        SELECT {_COLUMNS}
        FROM players
        {where_clause}
        ORDER BY created_at DESC, player_id DESC
        LIMIT %s OFFSET %s
        """,
        parameters,
    ).fetchall()


@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(player_id: int, connection: DbConnection):
    return _player_or_404(connection, player_id)


@router.patch("/{player_id}", response_model=PlayerResponse)
def update_player(
    player_id: int,
    payload: PlayerUpdate,
    connection: DbConnection,
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update.",
        )

    allowed_fields = {"username", "display_name", "email"}
    if not set(changes).issubset(allowed_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported update field.",
        )

    try:
        with connection.transaction():
            _player_or_404(connection, player_id)
            assignments = ", ".join(f"{column} = %s" for column in changes)
            values = list(changes.values()) + [player_id]
            row = connection.execute(
                f"""
                UPDATE players
                SET {assignments}
                WHERE player_id = %s
                RETURNING player_id, username, display_name, email, created_at
                """,
                values,
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row
