"""Integration tests for the tournament HTTP API."""

import os
import uuid
from collections.abc import Generator

import psycopg
import pytest
from app.db.connection import get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def dsn() -> str:
    value = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set NEXUSMATCH_TEST_DATABASE_URL to run database API tests")
    return value


@pytest.fixture
def api(dsn: str) -> Generator[TestClient, None, None]:
    def override_get_db():
        with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as connection:
            yield connection

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def suffix() -> str:
    return uuid.uuid4().hex[:12]


@pytest.fixture
def created_tournament(api: TestClient, dsn: str, suffix: str):
    payload = {
        "name": f"API Tournament {suffix}",
        "game_name": "Integration Test Game",
        "tournament_type": "individual",
        "format": "swiss",
        "max_entries": 8,
    }
    response = api.post("/api/v1/tournaments", json=payload)
    assert response.status_code == 201
    tournament = response.json()
    try:
        yield tournament
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "DELETE FROM tournaments WHERE tournament_id = %s",
                (tournament["tournament_id"],),
            )


def test_create_tournament(api: TestClient, dsn: str, suffix: str):
    response = api.post(
        "/api/v1/tournaments",
        json={
            "name": f"New Tournament {suffix}",
            "game_name": "Valorant",
            "tournament_type": "team",
            "format": "single_elimination",
            "max_entries": 16,
        },
    )
    assert response.status_code == 201
    data = response.json()
    try:
        assert data["tournament_type"] == "team"
        assert data["status"] == "draft"
        assert data["max_entries"] == 16
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "DELETE FROM tournaments WHERE tournament_id = %s",
                (data["tournament_id"],),
            )


def test_create_tournament_trims_name_and_persists_canonical_value(
    api: TestClient, dsn: str
):
    response = api.post(
        "/api/v1/tournaments",
        json={
            "name": "  Canonical API Tournament  ",
            "game_name": "Valorant",
            "tournament_type": "individual",
            "format": "single_elimination",
            "max_entries": 8,
        },
    )
    assert response.status_code == 201
    tournament = response.json()
    try:
        assert tournament["name"] == "Canonical API Tournament"
        with psycopg.connect(dsn) as connection:
            stored_name = connection.execute(
                "SELECT name FROM tournaments WHERE tournament_id = %s",
                (tournament["tournament_id"],),
            ).fetchone()[0]
        assert stored_name == tournament["name"]
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "DELETE FROM tournaments WHERE tournament_id = %s",
                (tournament["tournament_id"],),
            )


def test_create_tournament_rejects_invalid_payload(api: TestClient):
    response = api.post(
        "/api/v1/tournaments",
        json={
            "name": "x",
            "game_name": "",
            "tournament_type": "duo",
            "format": "swiss",
            "max_entries": 1,
        },
    )
    assert response.status_code == 422


def test_get_tournament(api: TestClient, created_tournament: dict):
    response = api.get(
        f"/api/v1/tournaments/{created_tournament['tournament_id']}"
    )
    assert response.status_code == 200
    assert response.json()["name"] == created_tournament["name"]


def test_missing_tournament_returns_404(api: TestClient):
    response = api.get("/api/v1/tournaments/9223372036854770000")
    assert response.status_code == 404


def test_list_tournaments_supports_filters_and_pagination(
    api: TestClient, created_tournament: dict
):
    response = api.get(
        "/api/v1/tournaments",
        params={
            "tournament_type": "individual",
            "status": "draft",
            "game_name": "Integration Test Game",
            "limit": 5,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    assert any(
        item["tournament_id"] == created_tournament["tournament_id"]
        for item in response.json()
    )


def test_update_tournament(api: TestClient, created_tournament: dict):
    response = api.patch(
        f"/api/v1/tournaments/{created_tournament['tournament_id']}",
        json={"name": "Updated Tournament", "status": "registration_open"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Tournament"
    assert response.json()["status"] == "registration_open"


def test_empty_update_is_rejected(api: TestClient, created_tournament: dict):
    response = api.patch(
        f"/api/v1/tournaments/{created_tournament['tournament_id']}",
        json={},
    )
    assert response.status_code == 422


def test_update_missing_tournament_returns_404(api: TestClient):
    response = api.patch(
        "/api/v1/tournaments/9223372036854770000",
        json={"name": "Does not exist"},
    )
    assert response.status_code == 404


def test_capacity_can_be_lowered_when_active_count_fits(
    api: TestClient, dsn: str, created_tournament: dict, suffix: str
):
    tournament_id = created_tournament["tournament_id"]
    with psycopg.connect(dsn) as connection:
        player_id = connection.execute(
            """
            INSERT INTO players (username, display_name)
            VALUES (%s, %s) RETURNING player_id
            """,
            (f"tourney_api_{suffix}", "Tournament API test player"),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO registrations (tournament_id, player_id)
            VALUES (%s, %s)
            """,
            (tournament_id, player_id),
        )

    response = api.patch(
        f"/api/v1/tournaments/{tournament_id}",
        json={"max_entries": 2},
    )
    assert response.status_code == 200
