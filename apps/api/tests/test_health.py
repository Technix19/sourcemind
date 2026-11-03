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


def test_unknown_route_is_404():
    assert client.get("/api/v1/nope").status_code == 404
