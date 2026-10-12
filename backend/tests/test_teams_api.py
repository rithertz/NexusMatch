"""Integration tests for the team HTTP API."""

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
def created_team(api: TestClient, dsn: str, suffix: str):
    payload = {"team_name": f"Team {suffix}"}
    response = api.post("/api/v1/teams", json=payload)
    assert response.status_code == 201
    team = response.json()
    try:
        yield team
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "DELETE FROM teams WHERE team_id = %s",
                (team["team_id"],),
            )


@pytest.fixture
def created_player(api: TestClient, dsn: str, suffix: str):
    response = api.post(
        "/api/v1/players",
        json={
            "username": f"team_member_{suffix}",
            "display_name": f"Team Member {suffix}",
            "email": f"team_member_{suffix}@example.com",
        },
    )
    assert response.status_code == 201
    player = response.json()
    try:
        yield player
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "DELETE FROM players WHERE player_id = %s",
                (player["player_id"],),
            )


def test_create_team(api: TestClient, suffix: str):
    response = api.post("/api/v1/teams", json={"team_name": f"New Team {suffix}"})
    assert response.status_code == 201
    assert response.json()["team_name"] == f"New Team {suffix}"


def test_get_team(api: TestClient, created_team: dict):
    response = api.get(f"/api/v1/teams/{created_team['team_id']}")
    assert response.status_code == 200
    assert response.json()["team_name"] == created_team["team_name"]


def test_missing_team_returns_404(api: TestClient):
    response = api.get("/api/v1/teams/9223372036854775807")
    assert response.status_code == 404


def test_update_team(api: TestClient, created_team: dict):
    response = api.patch(
        f"/api/v1/teams/{created_team['team_id']}",
        json={"team_name": "Updated Team Name"},
    )
    assert response.status_code == 200
    assert response.json()["team_name"] == "Updated Team Name"


def test_add_and_remove_team_member(api: TestClient, created_team: dict, created_player: dict):
    add_response = api.post(
        f"/api/v1/teams/{created_team['team_id']}/members",
        json={"player_id": created_player["player_id"]},
    )
    assert add_response.status_code == 201
    assert add_response.json()["player_id"] == created_player["player_id"]

    list_response = api.get(f"/api/v1/teams/{created_team['team_id']}/members")
    assert list_response.status_code == 200
    assert any(
        item["player_id"] == created_player["player_id"]
        for item in list_response.json()
    )

    delete_response = api.delete(
        f"/api/v1/teams/{created_team['team_id']}/members/{created_player['player_id']}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["player_id"] == created_player["player_id"]


def test_duplicate_team_member_is_rejected(api: TestClient, created_team: dict, created_player: dict):
    api.post(
        f"/api/v1/teams/{created_team['team_id']}/members",
        json={"player_id": created_player["player_id"]},
    )
    response = api.post(
        f"/api/v1/teams/{created_team['team_id']}/members",
        json={"player_id": created_player["player_id"]},
    )
    assert response.status_code == 409


def test_missing_player_for_team_membership_returns_404(api: TestClient, created_team: dict):
    response = api.post(
        f"/api/v1/teams/{created_team['team_id']}/members",
        json={"player_id": 9223372036854775807},
    )
    assert response.status_code == 404
