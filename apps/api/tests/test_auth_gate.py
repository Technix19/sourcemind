import asyncio

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth import PUBLIC_PATHS, AuthUnavailable, current_user
from app.main import app, check_configuration
from conftest import AUTH_A, AUTH_B, make_pdf

anonymous = TestClient(app)
alice = TestClient(app, headers=AUTH_A)
bob = TestClient(app, headers=AUTH_B)


def test_health_is_the_only_public_api_route():
    assert anonymous.get("/api/v1/health").status_code == 200
    assert PUBLIC_PATHS == {"/api/v1/health"}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": ""}, {"Authorization": "Bearer"}, {"Authorization": "Bearer "},
     {"Authorization": "Basic dXNlcjpwYXNz"}, {"Authorization": "Bearer not-a-real-token"},
     {"Authorization": "bearer"}],
)
def test_missing_or_invalid_credentials_get_401(headers):
    res = anonymous.get("/api/v1/documents", headers=headers)
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"
    assert res.json() == {"detail": "Not authenticated"}   # never says WHY (no oracle for attackers)


def test_every_protected_route_rejects_anonymous_callers():
    """Inventory test: a new route that forgets protection cannot slip in unnoticed."""
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/") or route.path in PUBLIC_PATHS:
            continue
        for method in route.methods:
            url = route.path.replace("{document_id}", "00000000-0000-0000-0000-000000000000")
            assert anonymous.request(method, url).status_code == 401, f"{method} {route.path} is unprotected"
            checked += 1
    assert checked >= 5   # upload, list, get, delete, query


def test_authentication_runs_before_request_validation():
    # With auth only as a dependency this would be a 422 (missing file / bad body).
    assert anonymous.post("/api/v1/documents").status_code == 401
    assert anonymous.post("/api/v1/queries", json={}).status_code == 401


def test_rejected_upload_is_not_read_at_all():
    """The reason auth is a gate: an anonymous 8 MB upload must cost the server ~nothing."""
    consumed = {"bytes": 0}

    async def counting_app(scope, receive, send):
        async def counted():
            message = await receive()
            if message["type"] == "http.request":
                consumed["bytes"] += len(message.get("body", b""))
            return message
        await app(scope, counted, send)

    async def attempt():
        transport = httpx.ASGITransport(app=counting_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/documents", files={"file": ("big.bin", b"x" * 8 * 1024 * 1024)})

    assert asyncio.run(attempt()).status_code == 401
    assert consumed["bytes"] == 0


def test_a_401_still_carries_cors_headers_so_the_browser_can_read_it():
    res = anonymous.get("/api/v1/documents", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 401
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_authorization_header_is_allowed_in_cors_preflight():
    res = anonymous.options(
        "/api/v1/documents",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "authorization"},
    )
    assert res.status_code == 200 and "authorization" in res.headers["access-control-allow-headers"].lower()


def test_current_user_fails_closed_if_the_gate_is_ever_missing():
    bare = FastAPI()   # no middleware at all

    @bare.get("/whoami")
    def whoami(user=Depends(current_user)):
        return {"id": user.id}

    assert TestClient(bare).get("/whoami").status_code == 401


def test_key_server_outage_is_a_503_not_a_misleading_401(monkeypatch):
    from app import auth

    class Down:
        def verify(self, token):
            raise AuthUnavailable("down")

    monkeypatch.setattr(auth, "get_verifier", lambda: Down())
    res = anonymous.get("/api/v1/documents", headers={"Authorization": "Bearer anything"})
    assert res.status_code == 503 and "unavailable" in res.json()["detail"].lower()


# ------------------------------------------------ two users through the real API

def upload(client, name="a.txt", data=b"The Random Forest classifier selects question difficulty."):
    res = client.post("/api/v1/documents", files={"file": (name, data)})
    assert res.status_code == 201, res.text
    return res.json()


def test_users_cannot_see_or_touch_each_others_documents():
    doc = upload(alice)
    assert [d["id"] for d in alice.get("/api/v1/documents").json()["documents"]] == [doc["id"]]
    assert bob.get("/api/v1/documents").json()["documents"] == []
    assert bob.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert bob.delete(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert alice.get(f"/api/v1/documents/{doc['id']}").status_code == 200   # untouched


def test_users_cannot_query_each_others_documents():
    doc = upload(alice)
    question = {"question": "Which classifier selects difficulty?"}
    assert bob.post("/api/v1/queries", json={**question, "document_ids": [doc["id"]]}).status_code == 404
    assert bob.post("/api/v1/queries", json=question).status_code == 409        # Bob has no documents
    own = alice.post("/api/v1/queries", json=question).json()
    assert own["evidence"] and own["evidence"][0]["document_id"] == doc["id"]


def test_each_user_has_their_own_document_limit(monkeypatch):
    monkeypatch.setenv("MAX_DOCUMENTS", "1")
    upload(alice, "1.txt")
    assert alice.post("/api/v1/documents", files={"file": ("2.txt", b"two")}).status_code == 409
    upload(bob, "1.txt")   # Alice being full does not affect Bob


# ------------------------------------------------------------ fail-closed startup

def test_startup_refuses_to_run_without_supabase_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="no anonymous mode"):
        check_configuration()


def test_startup_accepts_complete_settings_and_normalises_the_url(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co/rest/v1/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "distinctive-key-value-123")
    check_configuration()
    assert get_settings().supabase_url == "https://abc.supabase.co"
    assert "distinctive-key-value-123" not in repr(get_settings())   # keys never appear in logs via repr
