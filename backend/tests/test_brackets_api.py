"""Database-backed integration tests for single-elimination brackets."""

import os
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from app.db.connection import get_db
from app.main import app
from fastapi.testclient import TestClient
from psycopg.rows import dict_row


@pytest.fixture
def dsn() -> str:
    value = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not value:
        pytest.fail("NEXUSMATCH_TEST_DATABASE_URL is required for bracket tests")
    return value


@pytest.fixture
def api(dsn: str) -> Generator[TestClient, None, None]:
    def override_get_db():
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            yield connection

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def create_tournament(
    dsn: str,
    *,
    entrant_count: int,
    suffix: str | None = None,
    tournament_type: str = "individual",
    tournament_format: str = "single_elimination",
    tournament_status: str = "registration_open",
    registration_statuses: list[str] | None = None,
) -> dict:
    suffix = suffix or uuid.uuid4().hex[:12]
    registration_statuses = registration_statuses or ["approved"] * entrant_count
    with psycopg.connect(dsn) as connection:
        tournament_id = connection.execute(
            """
            INSERT INTO tournaments
                (name, game_name, tournament_type, format, status, max_entries)
            VALUES (%s, 'Bracket Test Game', %s, %s, %s, %s)
            RETURNING tournament_id
            """,
            (
                f"Bracket {suffix}",
                tournament_type,
                tournament_format,
                tournament_status,
                max(entrant_count, 2),
            ),
        ).fetchone()[0]

        registration_ids = []
        competitor_ids = []
        for index in range(entrant_count):
            if tournament_type == "individual":
                competitor_id = connection.execute(
                    """
                    INSERT INTO players (username, display_name)
                    VALUES (%s, %s)
                    RETURNING player_id
                    """,
                    (f"bracket_{suffix}_{index}", f"Player {index}"),
                ).fetchone()[0]
                player_id, team_id = competitor_id, None
            else:
                competitor_id = connection.execute(
                    """
                    INSERT INTO teams (team_name)
                    VALUES (%s)
                    RETURNING team_id
                    """,
                    (f"Bracket Team {suffix} {index}",),
                ).fetchone()[0]
                player_id, team_id = None, competitor_id

            registration_id = connection.execute(
                """
                INSERT INTO registrations
                    (tournament_id, player_id, team_id, status)
                VALUES (%s, %s, %s, %s)
                RETURNING registration_id
                """,
                (
                    tournament_id,
                    player_id,
                    team_id,
                    registration_statuses[index],
                ),
            ).fetchone()[0]
            registration_ids.append(registration_id)
            competitor_ids.append(competitor_id)

    return {
        "tournament_id": tournament_id,
        "registration_ids": registration_ids,
        "competitor_ids": competitor_ids,
        "suffix": suffix,
    }


def cleanup_tournament(dsn: str, tournament_id: int):
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "DELETE FROM tournaments WHERE tournament_id = %s",
            (tournament_id,),
        )


def create_bracket(api: TestClient, tournament_id: int):
    return api.post(f"/api/v1/tournaments/{tournament_id}/bracket")


@pytest.mark.parametrize("entrant_count", [2, 3, 4, 5, 6, 7, 8, 9])
def test_generation_creates_correct_rounds_match_count_and_byes(
    api: TestClient,
    dsn: str,
    entrant_count: int,
):
    records = create_tournament(dsn, entrant_count=entrant_count)
    try:
        response = create_bracket(api, records["tournament_id"])

        assert response.status_code == 201
        bracket = response.json()
        bracket_size = 1 << (entrant_count - 1).bit_length()
        expected_round_counts = [
            bracket_size >> round_number
            for round_number in range(1, bracket_size.bit_length())
        ]
        rounds = bracket["rounds"]
        assert [len(item["matches"]) for item in rounds] == expected_round_counts
        assert sum(expected_round_counts) == bracket_size - 1
        assert len(rounds[0]["matches"]) == bracket_size // 2

        first_round_byes = [
            match for match in rounds[0]["matches"] if match["is_bye"]
        ]
        assert len(first_round_byes) == bracket_size - entrant_count
        assert all(match["status"] == "completed" for match in first_round_byes)
        assert all(len(match["participants"]) == 1 for match in first_round_byes)
        assert all(
            participant["score"] is None and not participant["is_winner"]
            for match in first_round_byes
            for participant in match["participants"]
        )

        if len(rounds) > 1:
            advanced_ids = {
                participant["registration_id"]
                for match in rounds[1]["matches"]
                for participant in match["participants"]
            }
            assert advanced_ids == {
                records["registration_ids"][index]
                for index in range(bracket_size - entrant_count)
            }

        with psycopg.connect(dsn) as connection:
            tournament_status = connection.execute(
                "SELECT status FROM tournaments WHERE tournament_id = %s",
                (records["tournament_id"],),
            ).fetchone()[0]
        assert tournament_status == "in_progress"
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_bracket_supports_team_competitors_and_is_persisted(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(
        dsn,
        entrant_count=2,
        tournament_type="team",
    )
    try:
        created = create_bracket(api, records["tournament_id"])
        fetched = api.get(
            f"/api/v1/tournaments/{records['tournament_id']}/bracket"
        )

        assert created.status_code == 201
        assert fetched.status_code == 200
        participant = fetched.json()["rounds"][0]["matches"][0]["participants"][0]
        assert participant["competitor_type"] == "team"
        assert participant["competitor_id"] in records["competitor_ids"]
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_generation_excludes_non_approved_registrations(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(
        dsn,
        entrant_count=5,
        registration_statuses=[
            "approved",
            "approved",
            "pending",
            "rejected",
            "withdrawn",
        ],
    )
    try:
        response = create_bracket(api, records["tournament_id"])

        assert response.status_code == 201
        entrants = {
            participant["registration_id"]
            for round_data in response.json()["rounds"]
            for match in round_data["matches"]
            for participant in match["participants"]
        }
        assert entrants == set(records["registration_ids"][:2])
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_generation_rejects_insufficient_entrants_and_invalid_state(
    api: TestClient,
    dsn: str,
):
    insufficient = create_tournament(dsn, entrant_count=1)
    closed = create_tournament(
        dsn,
        entrant_count=2,
        tournament_status="draft",
    )
    unsupported = create_tournament(
        dsn,
        entrant_count=2,
        tournament_format="swiss",
    )
    try:
        response = create_bracket(api, insufficient["tournament_id"])
        assert response.status_code == 409
        assert "two approved" in response.json()["detail"]

        response = create_bracket(api, closed["tournament_id"])
        assert response.status_code == 409

        response = create_bracket(api, unsupported["tournament_id"])
        assert response.status_code == 422
    finally:
        for records in (insufficient, closed, unsupported):
            cleanup_tournament(dsn, records["tournament_id"])


def test_duplicate_generation_and_missing_bracket_responses(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=2)
    try:
        assert api.get(
            f"/api/v1/tournaments/{records['tournament_id']}/bracket"
        ).status_code == 404
        assert create_bracket(api, records["tournament_id"]).status_code == 201
        duplicate = create_bracket(api, records["tournament_id"])
        assert duplicate.status_code == 409
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_concurrent_bracket_generation_creates_one_bracket(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=4)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda _: create_bracket(api, records["tournament_id"]),
                    range(2),
                )
            )
        assert sorted(response.status_code for response in responses) == [201, 409]

        with psycopg.connect(dsn) as connection:
            match_count = connection.execute(
                "SELECT COUNT(*) FROM matches WHERE tournament_id = %s",
                (records["tournament_id"],),
            ).fetchone()[0]
        assert match_count == 3
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_match_result_advances_winner_and_completes_tournament(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=4)
    try:
        bracket = create_bracket(api, records["tournament_id"]).json()
        first_match = bracket["rounds"][0]["matches"][0]
        first_ids = [
            participant["registration_id"]
            for participant in first_match["participants"]
        ]
        winner_id, loser_id = first_ids
        result = api.post(
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{first_match['match_id']}/result",
            json={
                "winner_registration_id": winner_id,
                "scores": [
                    {"registration_id": winner_id, "score": 2},
                    {"registration_id": loser_id, "score": 1},
                ],
            },
        )
        assert result.status_code == 200
        assert result.json()["winner_registration_id"] == winner_id

        updated = api.get(
            f"/api/v1/tournaments/{records['tournament_id']}/bracket"
        ).json()
        next_match = updated["rounds"][1]["matches"][0]
        assert winner_id in {
            participant["registration_id"]
            for participant in next_match["participants"]
        }

        second_match = updated["rounds"][0]["matches"][1]
        second_ids = [
            participant["registration_id"]
            for participant in second_match["participants"]
        ]
        second_winner, second_loser = second_ids
        response = api.post(
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{second_match['match_id']}/result",
            json={
                "winner_registration_id": second_winner,
                "scores": [
                    {"registration_id": second_winner, "score": 3},
                    {"registration_id": second_loser, "score": 1},
                ],
            },
        )
        assert response.status_code == 200

        final = api.get(
            f"/api/v1/tournaments/{records['tournament_id']}/bracket"
        ).json()["rounds"][1]["matches"][0]
        finalists = [
            participant["registration_id"] for participant in final["participants"]
        ]
        final_winner, final_loser = finalists
        response = api.post(
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{final['match_id']}/result",
            json={
                "winner_registration_id": final_winner,
                "scores": [
                    {"registration_id": final_winner, "score": 2},
                    {"registration_id": final_loser, "score": 0},
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["winner_registration_id"] == final_winner

        with psycopg.connect(dsn) as connection:
            tournament_status = connection.execute(
                "SELECT status FROM tournaments WHERE tournament_id = %s",
                (records["tournament_id"],),
            ).fetchone()[0]
        assert tournament_status == "completed"
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_bye_and_completed_matches_reject_results(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=3)
    try:
        bracket = create_bracket(api, records["tournament_id"]).json()
        bye = next(match for match in bracket["rounds"][0]["matches"] if match["is_bye"])
        response = api.post(
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{bye['match_id']}/result",
            json={
                "winner_registration_id": records["registration_ids"][0],
                "scores": [
                    {"registration_id": records["registration_ids"][0], "score": 1},
                    {"registration_id": records["registration_ids"][1], "score": 0},
                ],
            },
        )
        assert response.status_code == 409

        playable = next(
            match for match in bracket["rounds"][0]["matches"] if not match["is_bye"]
        )
        participant_ids = [
            participant["registration_id"] for participant in playable["participants"]
        ]
        payload = {
            "winner_registration_id": participant_ids[0],
            "scores": [
                {"registration_id": participant_ids[0], "score": 2},
                {"registration_id": participant_ids[1], "score": 1},
            ],
        }
        result_url = (
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{playable['match_id']}/result"
        )
        assert api.post(result_url, json=payload).status_code == 200
        overwritten = api.post(result_url, json=payload)
        assert overwritten.status_code == 409
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


@pytest.mark.parametrize(
    "payload",
    [
        {
            "winner_registration_id": 1,
            "scores": [
                {"registration_id": 1, "score": -1},
                {"registration_id": 2, "score": 1},
            ],
        },
        {
            "winner_registration_id": 1,
            "scores": [
                {"registration_id": 1, "score": 1},
                {"registration_id": 2, "score": 1},
            ],
        },
        {
            "winner_registration_id": 1,
            "scores": [
                {"registration_id": 1, "score": 1},
                {"registration_id": 1, "score": 2},
            ],
        },
        {
            "winner_registration_id": 1,
            "scores": [
                {"registration_id": 1, "score": 1},
                {"registration_id": 2, "score": 2},
            ],
        },
    ],
)
def test_invalid_scores_are_rejected(api: TestClient, payload: dict):
    response = api.post(
        "/api/v1/tournaments/1/matches/1/result",
        json=payload,
    )
    assert response.status_code == 422


def test_wrong_winner_or_cross_tournament_match_is_rejected(
    api: TestClient,
    dsn: str,
):
    first = create_tournament(dsn, entrant_count=2)
    second = create_tournament(dsn, entrant_count=2)
    try:
        first_match = create_bracket(api, first["tournament_id"]).json()["rounds"][0]["matches"][0]
        create_bracket(api, second["tournament_id"])
        participant_ids = [
            participant["registration_id"] for participant in first_match["participants"]
        ]
        mismatch = api.post(
            f"/api/v1/tournaments/{first['tournament_id']}/matches/"
            f"{first_match['match_id']}/result",
            json={
                "winner_registration_id": second["registration_ids"][0],
                "scores": [
                    {"registration_id": second["registration_ids"][0], "score": 2},
                    {"registration_id": participant_ids[0], "score": 1},
                ],
            },
        )
        assert mismatch.status_code == 422

        response = api.post(
            f"/api/v1/tournaments/{first['tournament_id']}/matches/"
            f"{first_match['match_id']}/result",
            json={
                "winner_registration_id": first["registration_ids"][0],
                "scores": [
                    {"registration_id": participant_ids[0], "score": 2},
                    {"registration_id": participant_ids[1], "score": 1},
                ],
            },
        )
        assert response.status_code == 200

        other_tournament_match = api.get(
            f"/api/v1/tournaments/{second['tournament_id']}/bracket"
        ).json()["rounds"][0]["matches"][0]
        wrong_context = api.post(
            f"/api/v1/tournaments/{first['tournament_id']}/matches/"
            f"{other_tournament_match['match_id']}/result",
            json={
                "winner_registration_id": second["registration_ids"][0],
                "scores": [
                    {"registration_id": second["registration_ids"][0], "score": 2},
                    {"registration_id": second["registration_ids"][1], "score": 1},
                ],
            },
        )
        assert wrong_context.status_code == 404
    finally:
        cleanup_tournament(dsn, first["tournament_id"])
        cleanup_tournament(dsn, second["tournament_id"])


def test_failed_advancement_rolls_back_match_result(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=4)
    try:
        bracket = create_bracket(api, records["tournament_id"]).json()
        first_match = bracket["rounds"][0]["matches"][0]
        winner_id, loser_id = [
            participant["registration_id"] for participant in first_match["participants"]
        ]
        next_match = bracket["rounds"][1]["matches"][0]
        with psycopg.connect(dsn) as connection:
            connection.execute(
                """
                INSERT INTO match_participants
                    (match_id, tournament_id, registration_id, slot_number)
                VALUES (%s, %s, %s, 1)
                """,
                (
                    next_match["match_id"],
                    records["tournament_id"],
                    records["registration_ids"][3],
                ),
            )

        response = api.post(
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{first_match['match_id']}/result",
            json={
                "winner_registration_id": winner_id,
                "scores": [
                    {"registration_id": winner_id, "score": 2},
                    {"registration_id": loser_id, "score": 0},
                ],
            },
        )
        assert response.status_code == 409

        with psycopg.connect(dsn) as connection:
            persisted = connection.execute(
                """
                SELECT matches.status, match_participants.score,
                       match_participants.is_winner
                FROM matches
                JOIN match_participants USING (match_id)
                WHERE matches.match_id = %s
                ORDER BY match_participants.slot_number
                """,
                (first_match["match_id"],),
            ).fetchall()
        assert all(row[0] == "scheduled" for row in persisted)
        assert all(row[1] is None and not row[2] for row in persisted)
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_concurrent_result_submissions_complete_only_once(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(dsn, entrant_count=4)
    try:
        bracket = create_bracket(api, records["tournament_id"]).json()
        match = bracket["rounds"][0]["matches"][0]
        next_match_id = bracket["rounds"][1]["matches"][0]["match_id"]
        first_id, second_id = [
            participant["registration_id"] for participant in match["participants"]
        ]
        url = (
            f"/api/v1/tournaments/{records['tournament_id']}/matches/"
            f"{match['match_id']}/result"
        )
        requests = [
            {
                "winner_registration_id": first_id,
                "scores": [
                    {"registration_id": first_id, "score": 2},
                    {"registration_id": second_id, "score": 1},
                ],
            },
            {
                "winner_registration_id": second_id,
                "scores": [
                    {"registration_id": first_id, "score": 1},
                    {"registration_id": second_id, "score": 2},
                ],
            },
        ]

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(lambda payload: api.post(url, json=payload), requests)
            )
        assert sorted(response.status_code for response in responses) == [200, 409]

        with psycopg.connect(dsn) as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM match_participants
                WHERE match_id = %s AND is_winner
                """,
                (match["match_id"],),
            ).fetchone()[0]
            next_match_slots = connection.execute(
                """
                SELECT slot_number, registration_id
                FROM match_participants
                WHERE match_id = %s
                """,
                (next_match_id,),
            ).fetchall()
        assert count == 1
        assert len(next_match_slots) == 1
        assert next_match_slots[0][0] == 1
        assert next_match_slots[0][1] in (first_id, second_id)
    finally:
        cleanup_tournament(dsn, records["tournament_id"])


def test_registrations_and_tournament_status_are_locked_after_generation(
    api: TestClient,
    dsn: str,
):
    records = create_tournament(
        dsn,
        entrant_count=3,
        registration_statuses=["approved", "approved", "pending"],
    )
    try:
        assert create_bracket(api, records["tournament_id"]).status_code == 201
        response = api.patch(
            f"/api/v1/registrations/{records['registration_ids'][2]}/status",
            json={"status": "approved"},
        )
        assert response.status_code == 409

        status_change = api.patch(
            f"/api/v1/tournaments/{records['tournament_id']}",
            json={"status": "registration_open"},
        )
        assert status_change.status_code == 409
        format_change = api.patch(
            f"/api/v1/tournaments/{records['tournament_id']}",
            json={"format": "swiss"},
        )
        assert format_change.status_code == 409
    finally:
        cleanup_tournament(dsn, records["tournament_id"])
