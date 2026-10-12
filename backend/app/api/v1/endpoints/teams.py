"""Team and team-membership endpoints."""

from collections.abc import Generator
from typing import Annotated

import psycopg
from app.db.connection import get_db
from app.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.errors import UniqueViolation

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])

DbConnection = Annotated[
    Generator[psycopg.Connection, None, None],
    Depends(get_db),
]

_COLUMNS = "team_id, team_name, created_at"
_MEMBER_COLUMNS = "team_id, player_id, joined_at"


def _team_or_404(connection: psycopg.Connection, team_id: int):
    row = connection.execute(
        f"SELECT {_COLUMNS} FROM teams WHERE team_id = %s",
        (team_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found.",
        )
    return row


def _player_or_404(connection: psycopg.Connection, player_id: int):
    row = connection.execute(
        "SELECT player_id FROM players WHERE player_id = %s",
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
        detail = "A team with this name already exists."
        message = str(exc).lower()
        if "team_name" in message:
            detail = "A team with this name already exists."
        elif "team_id" in message or "player_id" in message:
            detail = "This player is already a member of this team."
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The team could not be saved.",
    )


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_team(payload: TeamCreate, connection: DbConnection):
    try:
        with connection.transaction():
            row = connection.execute(
                """
                INSERT INTO teams (team_name)
                VALUES (%s)
                RETURNING team_id, team_name, created_at
                """,
                (payload.team_name.strip(),),
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row


@router.get("", response_model=list[TeamResponse])
def list_teams(
    connection: DbConnection,
    team_name: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions: list[str] = []
    parameters: list[object] = []

    if team_name is not None:
        conditions.append("LOWER(team_name) = LOWER(%s)")
        parameters.append(team_name.strip())

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    parameters.extend([limit, offset])

    return connection.execute(
        f"""
        SELECT {_COLUMNS}
        FROM teams
        {where_clause}
        ORDER BY created_at DESC, team_id DESC
        LIMIT %s OFFSET %s
        """,
        parameters,
    ).fetchall()


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, connection: DbConnection):
    return _team_or_404(connection, team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    connection: DbConnection,
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update.",
        )

    if set(changes) != {"team_name"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported update field.",
        )

    try:
        with connection.transaction():
            _team_or_404(connection, team_id)
            value = next(iter(changes.values()))
            row = connection.execute(
                """
                UPDATE teams
                SET team_name = %s
                WHERE team_id = %s
                RETURNING team_id, team_name, created_at
                """,
                (value, team_id),
            ).fetchone()
    except psycopg.Error as exc:
        raise _database_error(exc) from exc
    return row


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
def list_team_members(team_id: int, connection: DbConnection):
    _team_or_404(connection, team_id)
    return connection.execute(
        f"""
        SELECT {_MEMBER_COLUMNS}
        FROM team_members
        WHERE team_id = %s
        ORDER BY joined_at DESC, player_id DESC
        """,
        (team_id,),
    ).fetchall()


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    team_id: int,
    payload: TeamMemberCreate,
    connection: DbConnection,
):
    try:
        with connection.transaction():
            _team_or_404(connection, team_id)
            _player_or_404(connection, payload.player_id)
            row = connection.execute(
                """
                INSERT INTO team_members (team_id, player_id)
                VALUES (%s, %s)
                RETURNING team_id, player_id, joined_at
                """,
                (team_id, payload.player_id),
            ).fetchone()
    except psycopg.Error as exc:
        if isinstance(exc, UniqueViolation):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This player is already a member of the team.",
            ) from exc
        raise _database_error(exc) from exc
    return row


@router.delete("/{team_id}/members/{player_id}", response_model=TeamMemberResponse)
def remove_team_member(team_id: int, player_id: int, connection: DbConnection):
    with connection.transaction():
        _team_or_404(connection, team_id)
        _player_or_404(connection, player_id)
        row = connection.execute(
            """
            DELETE FROM team_members
            WHERE team_id = %s AND player_id = %s
            RETURNING team_id, player_id, joined_at
            """,
            (team_id, player_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This player is not a member of the team.",
            )
    return row
