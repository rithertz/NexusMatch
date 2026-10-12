"""Tournament registration endpoints."""

from collections.abc import Generator
from typing import Annotated

import psycopg
from app.db.connection import get_db
from app.schemas.registration import (
    RegistrationCreate,
    RegistrationResponse,
    RegistrationStatusUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.errors import ForeignKeyViolation, RaiseException, UniqueViolation

router = APIRouter(prefix="/api/v1/registrations", tags=["Registrations"])

DbConnection = Annotated[
    Generator[psycopg.Connection, None, None],
    Depends(get_db),
]


def _registration_or_404(
    connection,
    registration_id: int,
    *,
    for_update: bool = False,
):
    lock_clause = "FOR UPDATE" if for_update else ""

    row = connection.execute(
        f"""
        SELECT registration_id, tournament_id, player_id, team_id,
               status, registered_at
        FROM registrations
        WHERE registration_id = %s
        {lock_clause}
        """,
        (registration_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found.",
        )

    return row

def _insert_error(exc: psycopg.Error) -> HTTPException:
    if isinstance(exc, UniqueViolation):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This competitor is already registered for the tournament.",
        )

    if isinstance(exc, ForeignKeyViolation):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified tournament, player, or team does not exist.",
        )

    if isinstance(exc, RaiseException):
        message = str(exc).lower()

        if "full" in message:
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The tournament has reached its registration capacity.",
            )

        if "require a player" in message or "require a team" in message:
            return HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The competitor type does not match the tournament type.",
            )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The registration could not be saved.",
    )


@router.post(
    "",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registration(
    payload: RegistrationCreate,
    connection: DbConnection,
):
    tournament = connection.execute(
        """
        SELECT tournament_id, tournament_type, status
        FROM tournaments
        WHERE tournament_id = %s
        """,
        (payload.tournament_id,),
    ).fetchone()

    if tournament is None:
        raise HTTPException(404, "Tournament not found.")

    if tournament["status"] != "registration_open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration is not open for this tournament.",
        )

    if tournament["tournament_type"] == "individual" and payload.player_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Individual tournaments require player_id.",
        )

    if tournament["tournament_type"] == "team" and payload.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Team tournaments require team_id.",
        )

    try:
        with connection.transaction():
            row = connection.execute(
                """
                INSERT INTO registrations
                    (tournament_id, player_id, team_id)
                VALUES (%s, %s, %s)
                RETURNING registration_id, tournament_id, player_id,
                          team_id, status, registered_at
                """,
                (
                    payload.tournament_id,
                    payload.player_id,
                    payload.team_id,
                ),
            ).fetchone()
    except psycopg.Error as exc:
        raise _insert_error(exc) from exc

    return row


@router.get("", response_model=list[RegistrationResponse])
def list_registrations(
    connection: DbConnection,
    tournament_id: int | None = Query(default=None, ge=1),
    registration_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|approved|rejected|withdrawn)$",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions = []
    parameters = []

    if tournament_id is not None:
        conditions.append("tournament_id = %s")
        parameters.append(tournament_id)

    if registration_status is not None:
        conditions.append("status = %s")
        parameters.append(registration_status)

    where_clause = (
        "WHERE " + " AND ".join(conditions) if conditions else ""
    )

    parameters.extend([limit, offset])

    return connection.execute(
        f"""
        SELECT registration_id, tournament_id, player_id, team_id,
               status, registered_at
        FROM registrations
        {where_clause}
        ORDER BY registered_at DESC, registration_id DESC
        LIMIT %s OFFSET %s
        """,
        parameters,
    ).fetchall()


@router.get("/{registration_id}", response_model=RegistrationResponse)
def get_registration(
    registration_id: int,
    connection: DbConnection,
):
    return _registration_or_404(connection, registration_id)


@router.patch(
    "/{registration_id}/status",
    response_model=RegistrationResponse,
)
def update_registration_status(
    registration_id: int,
    payload: RegistrationStatusUpdate,
    connection: DbConnection,
):
    try:
        with connection.transaction():
            current = _registration_or_404(connection, registration_id, for_update=True,)

            if current["status"] != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only pending registrations can be approved or rejected.",
                )

            row = connection.execute(
                """
                UPDATE registrations
                SET status = %s
                WHERE registration_id = %s
                RETURNING registration_id, tournament_id, player_id,
                          team_id, status, registered_at
                """,
                (payload.status, registration_id),
            ).fetchone()
    except psycopg.Error as exc:
        raise _insert_error(exc) from exc

    return row


@router.post(
    "/{registration_id}/withdraw",
    response_model=RegistrationResponse,
)
def withdraw_registration(
    registration_id: int,
    connection: DbConnection,
):
    try:
        with connection.transaction():
            current = _registration_or_404(connection, registration_id, for_update=True,)

            if current["status"] not in ("pending", "approved"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only pending or approved registrations can be withdrawn.",
                )

            row = connection.execute(
                """
                UPDATE registrations
                SET status = 'withdrawn'
                WHERE registration_id = %s
                RETURNING registration_id, tournament_id, player_id,
                          team_id, status, registered_at
                """,
                (registration_id,),
            ).fetchone()
    except psycopg.Error as exc:
        raise _insert_error(exc) from exc

    return row