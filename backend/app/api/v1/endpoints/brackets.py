"""Single-elimination bracket generation and match-result endpoints."""

from collections.abc import Generator
from typing import Annotated

import psycopg
from app.db.connection import get_db
from app.schemas.bracket import (
    BracketMatchResponse,
    BracketParticipantResponse,
    BracketResponse,
    BracketRoundResponse,
    MatchResultCreate,
)
from app.services.bracket import bracket_round_sizes, first_round_pairings
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    RaiseException,
    UniqueViolation,
)

router = APIRouter(prefix="/api/v1/tournaments", tags=["Brackets"])

DbConnection = Annotated[
    Generator[psycopg.Connection, None, None],
    Depends(get_db),
]

_MATCH_SELECT = """
    SELECT
        matches.match_id,
        matches.round_number,
        matches.match_number,
        matches.status,
        matches.is_bye,
        matches.scheduled_at,
        matches.started_at,
        matches.completed_at,
        match_participants.registration_id,
        match_participants.slot_number,
        match_participants.score,
        match_participants.is_winner,
        CASE
            WHEN registrations.player_id IS NOT NULL THEN 'player'
            ELSE 'team'
        END AS competitor_type,
        COALESCE(players.display_name, teams.team_name) AS display_name,
        COALESCE(registrations.player_id, registrations.team_id) AS competitor_id
    FROM matches
    LEFT JOIN match_participants
        ON match_participants.match_id = matches.match_id
       AND match_participants.tournament_id = matches.tournament_id
    LEFT JOIN registrations
        ON registrations.registration_id = match_participants.registration_id
       AND registrations.tournament_id = match_participants.tournament_id
    LEFT JOIN players ON players.player_id = registrations.player_id
    LEFT JOIN teams ON teams.team_id = registrations.team_id
"""


def _match_responses(rows) -> list[BracketMatchResponse]:
    matches: dict[int, dict] = {}

    for row in rows:
        match = matches.setdefault(
            row["match_id"],
            {
                "match_id": row["match_id"],
                "round_number": row["round_number"],
                "match_number": row["match_number"],
                "status": row["status"],
                "is_bye": row["is_bye"],
                "scheduled_at": row["scheduled_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "winner_registration_id": None,
                "participants": [],
            },
        )

        if row["registration_id"] is None:
            continue

        participant = BracketParticipantResponse(
            registration_id=row["registration_id"],
            slot_number=row["slot_number"],
            competitor_type=row["competitor_type"],
            competitor_id=row["competitor_id"],
            display_name=row["display_name"],
            score=row["score"],
            is_winner=row["is_winner"],
        )
        match["participants"].append(participant)
        if participant.is_winner:
            match["winner_registration_id"] = participant.registration_id

    return [BracketMatchResponse(**match) for match in matches.values()]


def _fetch_matches(
    connection: psycopg.Connection,
    tournament_id: int,
    *,
    match_id: int | None = None,
) -> list[BracketMatchResponse]:
    condition = "WHERE matches.tournament_id = %s"
    parameters: list[int] = [tournament_id]
    if match_id is not None:
        condition += " AND matches.match_id = %s"
        parameters.append(match_id)

    rows = connection.execute(
        f"""
        {_MATCH_SELECT}
        {condition}
        ORDER BY matches.round_number, matches.match_number,
                 match_participants.slot_number
        """,
        parameters,
    ).fetchall()
    return _match_responses(rows)


def _database_conflict(exc: psycopg.Error) -> HTTPException:
    if isinstance(
        exc,
        (CheckViolation, ForeignKeyViolation, RaiseException, UniqueViolation),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The bracket state conflicts with existing tournament data.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The bracket operation could not be completed.",
    )


@router.post(
    "/{tournament_id}/bracket",
    response_model=BracketResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_bracket(tournament_id: int, connection: DbConnection):
    try:
        with connection.transaction():
            tournament = connection.execute(
                """
                SELECT tournament_id, tournament_type, format, status
                FROM tournaments
                WHERE tournament_id = %s
                FOR UPDATE
                """,
                (tournament_id,),
            ).fetchone()
            if tournament is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tournament not found.",
                )
            if tournament["format"] != "single_elimination":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Bracket generation supports single-elimination tournaments only.",
                )
            existing_bracket = connection.execute(
                "SELECT 1 FROM matches WHERE tournament_id = %s LIMIT 1",
                (tournament_id,),
            ).fetchone()
            if existing_bracket is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A bracket has already been generated for this tournament.",
                )
            if tournament["status"] != "registration_open":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The tournament must be registration_open to generate its bracket.",
                )

            registrations = connection.execute(
                """
                SELECT registration_id
                FROM registrations
                WHERE tournament_id = %s AND status = 'approved'
                ORDER BY registered_at, registration_id
                """,
                (tournament_id,),
            ).fetchall()
            registration_ids = [row["registration_id"] for row in registrations]
            if len(registration_ids) < 2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="At least two approved registrations are required.",
                )

            round_sizes = bracket_round_sizes(len(registration_ids))
            first_round = first_round_pairings(registration_ids)
            bye_matches = {
                pairing.match_number for pairing in first_round if pairing.is_bye
            }

            match_rows = [
                (
                    tournament_id,
                    round_number,
                    match_number,
                    "completed"
                    if round_number == 1 and match_number in bye_matches
                    else "scheduled",
                    round_number == 1 and match_number in bye_matches,
                )
                for round_number, match_count in enumerate(round_sizes, start=1)
                for match_number in range(1, match_count + 1)
            ]
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO matches
                        (tournament_id, round_number, match_number, status, is_bye)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    match_rows,
                )

            match_ids = {
                (row["round_number"], row["match_number"]): row["match_id"]
                for row in connection.execute(
                    """
                    SELECT match_id, round_number, match_number
                    FROM matches
                    WHERE tournament_id = %s
                    """,
                    (tournament_id,),
                ).fetchall()
            }

            participant_rows: list[tuple[int, int, int, int]] = []
            for pairing in first_round:
                match_id = match_ids[(1, pairing.match_number)]
                for slot_number, registration_id in enumerate(
                    pairing.registration_ids, start=1
                ):
                    participant_rows.append(
                        (match_id, tournament_id, registration_id, slot_number)
                    )

                if pairing.is_bye and len(round_sizes) > 1:
                    next_round_match = (pairing.match_number + 1) // 2
                    next_round_slot = 1 if pairing.match_number % 2 else 2
                    participant_rows.append(
                        (
                            match_ids[(2, next_round_match)],
                            tournament_id,
                            pairing.registration_ids[0],
                            next_round_slot,
                        )
                    )

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO match_participants
                        (match_id, tournament_id, registration_id, slot_number)
                    VALUES (%s, %s, %s, %s)
                    """,
                    participant_rows,
                )

            connection.execute(
                """
                UPDATE tournaments
                SET status = 'in_progress'
                WHERE tournament_id = %s
                """,
                (tournament_id,),
            )
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise _database_conflict(exc) from exc

    return _load_bracket(connection, tournament_id)


def _load_bracket(
    connection: psycopg.Connection,
    tournament_id: int,
) -> BracketResponse:
    tournament = connection.execute(
        "SELECT tournament_id FROM tournaments WHERE tournament_id = %s",
        (tournament_id,),
    ).fetchone()
    if tournament is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found.",
        )

    matches = _fetch_matches(connection, tournament_id)
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The tournament bracket has not been generated.",
        )

    rounds: dict[int, list[BracketMatchResponse]] = {}
    for match in matches:
        rounds.setdefault(match.round_number, []).append(match)

    return BracketResponse(
        tournament_id=tournament_id,
        rounds=[
            BracketRoundResponse(round_number=round_number, matches=round_matches)
            for round_number, round_matches in rounds.items()
        ],
    )


@router.get("/{tournament_id}/bracket", response_model=BracketResponse)
def get_bracket(tournament_id: int, connection: DbConnection):
    return _load_bracket(connection, tournament_id)


@router.post(
    "/{tournament_id}/matches/{match_id}/result",
    response_model=BracketMatchResponse,
)
def submit_match_result(
    tournament_id: int,
    match_id: int,
    payload: MatchResultCreate,
    connection: DbConnection,
):
    try:
        with connection.transaction():
            tournament = connection.execute(
                """
                SELECT tournament_id, format, status
                FROM tournaments
                WHERE tournament_id = %s
                FOR UPDATE
                """,
                (tournament_id,),
            ).fetchone()
            if tournament is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tournament not found.",
                )

            match = connection.execute(
                """
                SELECT match_id, round_number, match_number, status, is_bye
                FROM matches
                WHERE match_id = %s AND tournament_id = %s
                FOR UPDATE
                """,
                (match_id, tournament_id),
            ).fetchone()
            if match is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Match not found in this tournament.",
                )
            if tournament["format"] != "single_elimination":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Results are supported only for single-elimination brackets.",
                )
            if tournament["status"] != "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The tournament is not in progress.",
                )
            if match["is_bye"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bye matches do not accept results.",
                )
            if match["status"] == "completed":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Completed match results cannot be overwritten.",
                )
            if match["status"] != "scheduled":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This match is not playable.",
                )

            participants = connection.execute(
                """
                SELECT registration_id, slot_number
                FROM match_participants
                WHERE match_id = %s AND tournament_id = %s
                ORDER BY slot_number
                FOR UPDATE
                """,
                (match_id, tournament_id),
            ).fetchall()
            participant_ids = {row["registration_id"] for row in participants}
            submitted_ids = {score.registration_id for score in payload.scores}
            if len(participant_ids) != 2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Both match participants must be determined before recording a result.",
                )
            if submitted_ids != participant_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Scores must correspond exactly to the match participants.",
                )
            if payload.winner_registration_id not in participant_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The winner must be a participant in this match.",
                )

            maximum_round = connection.execute(
                """
                SELECT MAX(round_number) AS maximum_round
                FROM matches
                WHERE tournament_id = %s
                """,
                (tournament_id,),
            ).fetchone()["maximum_round"]

            next_match = None
            if match["round_number"] < maximum_round:
                next_match_number = (match["match_number"] + 1) // 2
                next_match = connection.execute(
                    """
                    SELECT match_id
                    FROM matches
                    WHERE tournament_id = %s
                      AND round_number = %s
                      AND match_number = %s
                    FOR UPDATE
                    """,
                    (
                        tournament_id,
                        match["round_number"] + 1,
                        next_match_number,
                    ),
                ).fetchone()
                if next_match is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="The next-round match is missing from the bracket.",
                    )

            for score in payload.scores:
                connection.execute(
                    """
                    UPDATE match_participants
                    SET score = %s, is_winner = (registration_id = %s)
                    WHERE match_id = %s
                      AND tournament_id = %s
                      AND registration_id = %s
                    """,
                    (
                        score.score,
                        payload.winner_registration_id,
                        match_id,
                        tournament_id,
                        score.registration_id,
                    ),
                )

            connection.execute(
                """
                UPDATE matches
                SET status = 'completed',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    completed_at = CURRENT_TIMESTAMP
                WHERE match_id = %s AND tournament_id = %s
                """,
                (match_id, tournament_id),
            )

            if next_match is not None:
                next_slot = 1 if match["match_number"] % 2 else 2
                connection.execute(
                    """
                    INSERT INTO match_participants
                        (match_id, tournament_id, registration_id, slot_number)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        next_match["match_id"],
                        tournament_id,
                        payload.winner_registration_id,
                        next_slot,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE tournaments
                    SET status = 'completed'
                    WHERE tournament_id = %s
                    """,
                    (tournament_id,),
                )
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise _database_conflict(exc) from exc

    matches = _fetch_matches(connection, tournament_id, match_id=match_id)
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The completed match could not be retrieved.",
        )
    return matches[0]
