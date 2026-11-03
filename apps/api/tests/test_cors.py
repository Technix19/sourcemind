from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ALLOWED = "http://localhost:3000"


def preflight(origin: str, method: str = "POST"):
    return client.options(
        "/api/v1/queries",
        headers={"Origin": origin, "Access-Control-Request-Method": method,
                 "Access-Control-Request-Headers": "content-type"},
    )


def test_configured_frontend_origin_is_allowed():
    res = preflight(ALLOWED)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == ALLOWED


def test_other_origins_are_not_allowed():
    res = preflight("http://evil.example")
    assert "access-control-allow-origin" not in res.headers


def test_simple_requests_carry_the_header_only_for_the_allowed_origin():
    ok = client.get("/api/v1/health", headers={"Origin": ALLOWED})
    bad = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert ok.headers["access-control-allow-origin"] == ALLOWED
    assert "access-control-allow-origin" not in bad.headers


def test_no_credentials_and_no_unexpected_methods():
    res = preflight(ALLOWED, method="PUT")
    assert res.status_code == 400  # PUT is not an allowed method
    assert "access-control-allow-credentials" not in preflight(ALLOWED).headers
