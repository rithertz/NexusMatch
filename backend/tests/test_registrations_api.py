"""HTTP integration tests for registration endpoints."""

import os
import uuid

import psycopg
import pytest
from app.db.connection import get_db
from app.main import app
from fastapi.testclient import TestClient
from psycopg.rows import dict_row


@pytest.fixture
def api():
    dsn = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set NEXUSMATCH_TEST_DATABASE_URL to run API tests")

    def override_get_db():
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            yield connection

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def records():
    dsn = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set NEXUSMATCH_TEST_DATABASE_URL to run API tests")

    suffix = uuid.uuid4().hex[:12]
    player_id = None
    team_id = None
    tournament_id = None

    try:
        with psycopg.connect(dsn) as connection:
            player_id = connection.execute(
                """
                INSERT INTO players (username, display_name)
                VALUES (%s, %s)
                RETURNING player_id
                """,
                (f"api_{suffix}", f"API Test {suffix}"),
            ).fetchone()[0]

            team_id = connection.execute(
                """
                INSERT INTO teams (team_name)
                VALUES (%s)
                RETURNING team_id
                """,
                (f"api_team_{suffix}",),
            ).fetchone()[0]

            tournament_id = connection.execute(
                """
                INSERT INTO tournaments
                    (name, game_name, tournament_type, format,
                     status, max_entries)
                VALUES (%s, 'API Test Game', 'individual', 'swiss',
                        'registration_open', 4)
                RETURNING tournament_id
                """,
                (f"api_tournament_{suffix}",),
            ).fetchone()[0]

        yield {
            "player_id": player_id,
            "team_id": team_id,
            "tournament_id": tournament_id,
            "suffix": suffix,
        }
    finally:
        with psycopg.connect(dsn) as connection:
            if tournament_id is not None:
                connection.execute(
                    "DELETE FROM tournaments WHERE tournament_id = %s",
                    (tournament_id,),
                )
            if team_id is not None:
                connection.execute(
                    "DELETE FROM teams WHERE team_id = %s",
                    (team_id,),
                )
            if player_id is not None:
                connection.execute(
                    "DELETE FROM players WHERE player_id = %s",
                    (player_id,),
                )


def register(api, records):
    return api.post(
        "/api/v1/registrations",
        json={
            "tournament_id": records["tournament_id"],
            "player_id": records["player_id"],
        },
    )


def test_create_and_get_registration(api, records):
    response = register(api, records)

    assert response.status_code == 201
    registration = response.json()
    assert registration["tournament_id"] == records["tournament_id"]
    assert registration["player_id"] == records["player_id"]
    assert registration["status"] == "pending"

    detail = api.get(
        f"/api/v1/registrations/{registration['registration_id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["registration_id"] == registration["registration_id"]


def test_list_registrations_with_filters_and_pagination(api, records):
    created = register(api, records)
    assert created.status_code == 201

    response = api.get(
        "/api/v1/registrations",
        params={
            "tournament_id": records["tournament_id"],
            "status": "pending",
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["registration_id"] == created.json()[
        "registration_id"
    ]


def test_duplicate_registration_returns_conflict(api, records):
    assert register(api, records).status_code == 201

    duplicate = register(api, records)
    assert duplicate.status_code == 409


def test_missing_tournament_returns_not_found(api, records):
    response = api.post(
        "/api/v1/registrations",
        json={
            "tournament_id": 999999999,
            "player_id": records["player_id"],
        },
    )
    assert response.status_code == 404


def test_invalid_competitor_payload_returns_unprocessable(api, records):
    response = api.post(
        "/api/v1/registrations",
        json={
            "tournament_id": records["tournament_id"],
            "player_id": records["player_id"],
            "team_id": records["team_id"],
        },
    )
    assert response.status_code == 422


def test_closed_tournament_rejects_registration(api, records):
    dsn = os.environ["NEXUSMATCH_TEST_DATABASE_URL"]
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "UPDATE tournaments SET status = 'draft' WHERE tournament_id = %s",
            (records["tournament_id"],),
        )

    response = register(api, records)
    assert response.status_code == 409


def test_individual_tournament_rejects_team_registration(api, records):
    response = api.post(
        "/api/v1/registrations",
        json={
            "tournament_id": records["tournament_id"],
            "team_id": records["team_id"],
        },
    )
    assert response.status_code == 422


def test_missing_registration_returns_not_found(api):
    response = api.get("/api/v1/registrations/999999999")
    assert response.status_code == 404


def test_approve_then_withdraw_registration(api, records):
    created = register(api, records)
    registration_id = created.json()["registration_id"]

    approved = api.patch(
        f"/api/v1/registrations/{registration_id}/status",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    withdrawn = api.post(
        f"/api/v1/registrations/{registration_id}/withdraw"
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"


def test_reject_registration(api, records):
    created = register(api, records)
    registration_id = created.json()["registration_id"]

    response = api.patch(
        f"/api/v1/registrations/{registration_id}/status",
        json={"status": "rejected"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_rejected_registration_cannot_be_withdrawn(api, records):
    created = register(api, records)
    registration_id = created.json()["registration_id"]

    rejected = api.patch(
        f"/api/v1/registrations/{registration_id}/status",
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200

    withdrawn = api.post(
        f"/api/v1/registrations/{registration_id}/withdraw"
    )
    assert withdrawn.status_code == 409


def test_approved_registration_cannot_be_approved_again(api, records):
    created = register(api, records)
    registration_id = created.json()["registration_id"]

    first = api.patch(
        f"/api/v1/registrations/{registration_id}/status",
        json={"status": "approved"},
    )
    assert first.status_code == 200

    second = api.patch(
        f"/api/v1/registrations/{registration_id}/status",
        json={"status": "approved"},
    )
    assert second.status_code == 409


def test_registration_capacity_returns_conflict(api, records):
    dsn = os.environ["NEXUSMATCH_TEST_DATABASE_URL"]

    with psycopg.connect(dsn) as connection:
        connection.execute(
            "UPDATE tournaments SET max_entries = 2 WHERE tournament_id = %s",
            (records["tournament_id"],),
        )

        for index in range(3):
            player_id = connection.execute(
                """
                INSERT INTO players (username, display_name)
                VALUES (%s, %s)
                RETURNING player_id
                """,
                (
                    f"api_capacity_{records['suffix']}_{index}",
                    f"Capacity Test {index}",
                ),
            ).fetchone()[0]

            if index < 2:
                connection.execute(
                    """
                    INSERT INTO registrations (tournament_id, player_id)
                    VALUES (%s, %s)
                    """,
                    (records["tournament_id"], player_id),
                )

    new_player = None
    try:
        with psycopg.connect(dsn) as connection:
            new_player = connection.execute(
                """
                INSERT INTO players (username, display_name)
                VALUES (%s, %s)
                RETURNING player_id
                """,
                (
                    f"api_overflow_{records['suffix']}",
                    "Capacity Overflow",
                ),
            ).fetchone()[0]

        response = api.post(
            "/api/v1/registrations",
            json={
                "tournament_id": records["tournament_id"],
                "player_id": new_player,
            },
        )
        assert response.status_code == 409
    finally:
        if new_player is not None:
            with psycopg.connect(dsn) as connection:
                connection.execute(
                    "DELETE FROM players WHERE player_id = %s",
                    (new_player,),
                )