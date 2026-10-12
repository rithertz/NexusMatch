"""Tournament CRUD endpoints."""

from collections.abc import Generator
from typing import Annotated

import psycopg
from app.db.connection import get_db
from app.schemas.tournament import (
    TournamentCreate,
    TournamentResponse,
    TournamentStatus,
    TournamentUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.errors import ForeignKeyViolation, RaiseException, UniqueViolation

router = APIRouter(prefix="/api/v1/tournaments", tags=["Tournaments"])

DbConnection = Annotated[
    Generator[psycopg.Connection, None, None],
    Depends(get_db),
]

_COLUMNS = """
    tournament_id, name, game_name, tournament_type, format,
    status, max_entries, starts_at, created_at
"""


def _tournament_or_404(connection: psycopg.Connection, tournament_id: int):
    row = connection.execute(
        f"SELECT {_COLUMNS} FROM tournaments WHERE tournament_id = %s",
        (tournament_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found.",
        )
    return row


def _database_error(exc: psycopg.Error) -> HTTPException:
    if isinstance(exc, ForeignKeyViolation):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A referenced record does not exist.",
        )
    if isinstance(exc, (UniqueViolation, RaiseException)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The tournament update conflicts with existing database state.",
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The tournament could not be saved.",
    )


@router.post(
    "",
    response_model=TournamentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tournament(payload: TournamentCreate, connection: DbConnection):
    try:
        with connection.transaction():
            row = connection.execute(
                """
                INSERT INTO tournaments
                    (name, game_name, tournament_type, format, max_entries, starts_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING tournament_id, name, game_name, tournament_type,
                          format, status, max_entries, starts_at, created_at
                """,
                (
                    payload.name,
                    payload.game_name,
                    payload.tournament_type,
                    payload.format,
                    payload.max_entries,
                    payload.starts_at,
                ),
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row


@router.get("", response_model=list[TournamentResponse])
def list_tournaments(
    connection: DbConnection,
    tournament_type: str | None = Query(
        default=None, pattern="^(individual|team)$"
    ),
    tournament_status: Annotated[
        TournamentStatus | None,
        Query(alias="status"),
    ] = None,
    game_name: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions: list[str] = []
    parameters: list[object] = []

    if tournament_type is not None:
        conditions.append("tournament_type = %s")
        parameters.append(tournament_type)
    if tournament_status is not None:
        conditions.append("status = %s")
        parameters.append(tournament_status)
    if game_name is not None:
        conditions.append("LOWER(game_name) = LOWER(%s)")
        parameters.append(game_name.strip())

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    parameters.extend([limit, offset])
    return connection.execute(
        f"""
        SELECT {_COLUMNS}
        FROM tournaments
        {where_clause}
        ORDER BY created_at DESC, tournament_id DESC
        LIMIT %s OFFSET %s
        """,
        parameters,
    ).fetchall()


@router.get("/{tournament_id}", response_model=TournamentResponse)
def get_tournament(tournament_id: int, connection: DbConnection):
    return _tournament_or_404(connection, tournament_id)


@router.patch("/{tournament_id}", response_model=TournamentResponse)
def update_tournament(
    tournament_id: int,
    payload: TournamentUpdate,
    connection: DbConnection,
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update.",
        )

    # Explicit allowlist; identifiers and tournament_type are immutable here.
    allowed_fields = {"name", "game_name", "format", "max_entries", "starts_at", "status"}
    if not set(changes).issubset(allowed_fields):
        raise HTTPException(status_code=422, detail="Unsupported update field.")

    try:
        with connection.transaction():
            current = connection.execute(
                f"SELECT {_COLUMNS} FROM tournaments WHERE tournament_id = %s FOR UPDATE",
                (tournament_id,),
            ).fetchone()
            if current is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tournament not found.",
                )

            assignments = ", ".join(f"{column} = %s" for column in changes)
            values = list(changes.values()) + [tournament_id]
            row = connection.execute(
                f"""
                UPDATE tournaments
                SET {assignments}
                WHERE tournament_id = %s
                RETURNING {_COLUMNS}
                """,
                values,
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row
