import importlib

import pytest
from fastapi.testclient import TestClient

from app import main
from app.security import API_HEADERS, docs_settings


def test_health_and_rejections_carry_the_security_headers():
    client = TestClient(main.app)
    for response in (client.get("/api/v1/health"), client.get("/api/v1/documents")):  # 200 and 401
        for name, value in API_HEADERS.items():
            assert response.headers[name] == value


def test_api_policy_allows_nothing_to_load_or_frame():
    csp = API_HEADERS["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp


def test_docs_only_exist_locally():
    assert docs_settings("local")["docs_url"] == "/api/docs"
    for env in ("production", "staging", "", "Local-ish"):
        assert docs_settings(env) == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert docs_settings(" LOCAL ")["docs_url"] == "/api/docs"


def test_a_non_local_app_serves_no_docs_or_schema(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    try:
        deployed = importlib.reload(main)
        client = TestClient(deployed.app)
        assert client.get("/api/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
    finally:
        monkeypatch.undo()
        importlib.reload(main)


def test_local_docs_still_work_and_are_not_under_the_strict_policy():
    client = TestClient(main.app)
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
