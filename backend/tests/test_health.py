from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_when_both_databases_are_healthy(monkeypatch):
    monkeypatch.setattr("app.main.check_postgres", lambda: True)
    monkeypatch.setattr("app.main.check_mongodb", lambda: True)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "postgres": "ok",
            "mongodb": "ok",
        },
    }


def test_health_when_postgres_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.main.check_postgres", lambda: False)
    monkeypatch.setattr("app.main.check_mongodb", lambda: True)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == "error"


def test_health_when_mongodb_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.main.check_postgres", lambda: True)
    monkeypatch.setattr("app.main.check_mongodb", lambda: False)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["checks"]["mongodb"] == "error"
