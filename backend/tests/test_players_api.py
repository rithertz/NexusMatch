"""Integration tests for the player HTTP API."""

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
def created_player(api: TestClient, dsn: str, suffix: str):
    payload = {
        "username": f"player_{suffix}",
        "display_name": f"Player {suffix}",
        "email": f"{suffix}@example.com",
    }
    response = api.post("/api/v1/players", json=payload)
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


def test_create_player(api: TestClient, suffix: str):
    response = api.post(
        "/api/v1/players",
        json={
            "username": f"new_player_{suffix}",
            "display_name": f"New Player {suffix}",
            "email": f"new{suffix}@example.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"].startswith("new_player_")
    assert data["display_name"] == f"New Player {suffix}"


def test_get_player(api: TestClient, created_player: dict):
    response = api.get(f"/api/v1/players/{created_player['player_id']}")
    assert response.status_code == 200
    assert response.json()["username"] == created_player["username"]


def test_missing_player_returns_404(api: TestClient):
    response = api.get("/api/v1/players/9223372036854775807")
    assert response.status_code == 404


def test_list_players_supports_filters(api: TestClient, created_player: dict):
    response = api.get(
        "/api/v1/players",
        params={
            "username": created_player["username"],
            "limit": 10,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    assert any(
        item["player_id"] == created_player["player_id"]
        for item in response.json()
    )


def test_update_player(api: TestClient, created_player: dict):
    response = api.patch(
        f"/api/v1/players/{created_player['player_id']}",
        json={"display_name": "Updated Display Name"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Display Name"


def test_empty_player_update_is_rejected(api: TestClient, created_player: dict):
    response = api.patch(
        f"/api/v1/players/{created_player['player_id']}",
        json={},
    )
    assert response.status_code == 422


def test_duplicate_player_username_is_rejected(api: TestClient, created_player: dict):
    response = api.post(
        "/api/v1/players",
        json={
            "username": created_player["username"],
            "display_name": "Another Player",
            "email": "another@example.com",
        },
    )
    assert response.status_code == 409
