from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "version", "environment", "generation_available"}


def test_health_reflects_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    assert client.get("/api/v1/health").json()["environment"] == "test"


def test_unknown_route_does_not_reveal_itself_without_a_token():
    # Unauthenticated callers get 401 for any /api/v1/ path, existing or not.
    assert client.get("/api/v1/nope").status_code == 401
    # A signed-in user gets the honest answer.
    assert client.get("/api/v1/nope", headers={"Authorization": "Bearer user-a"}).status_code == 404
