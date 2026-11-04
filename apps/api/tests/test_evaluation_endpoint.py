import json

from fastapi.testclient import TestClient

from app.main import app
from conftest import AUTH_A

client = TestClient(app, headers=AUTH_A)
anonymous = TestClient(app)


def test_published_results_are_served_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    payload = {"schema": 1, "run": {"split": "test"}, "methods": {"tfidf": {"label": "Keyword"}}}
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("EVALUATION_RESULTS_PATH", str(path))
    res = client.get("/api/v1/evaluation/latest")
    assert res.status_code == 200 and res.json() == payload


def test_a_missing_results_file_is_a_clear_404(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALUATION_RESULTS_PATH", str(tmp_path / "nope.json"))
    res = client.get("/api/v1/evaluation/latest")
    assert res.status_code == 404 and "No evaluation results" in res.json()["detail"]


def test_a_corrupt_file_is_a_503_that_reveals_nothing(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    path.write_text("{ not json " + str(tmp_path))
    monkeypatch.setenv("EVALUATION_RESULTS_PATH", str(path))
    res = client.get("/api/v1/evaluation/latest")
    assert res.status_code == 503 and str(tmp_path) not in res.text


def test_the_route_requires_a_signed_in_user():
    assert anonymous.get("/api/v1/evaluation/latest").status_code == 401
