"""The whole API against the REAL Supabase project: real tokens, real database, two real users.

Nothing is faked here (the autouse fake backend skips tests marked `integration`).
"""
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthUser
from app.repository import RepositoryError, SupabaseRepository
from supabase_helpers import KEY, URL, rest, skip_without_supabase, user_a, user_b  # noqa: F401

pytestmark = [pytest.mark.integration, skip_without_supabase]

client = TestClient(main.app)
TEXT = b"The Random Forest classifier selects question difficulty for each learner."
QUESTION = {"question": "Which classifier selects difficulty?"}


def bearer(user):
    return {"Authorization": f"Bearer {user.token}"}


def upload(user, name="notes.txt", data=TEXT):
    res = client.post("/api/v1/documents", files={"file": (name, data)}, headers=bearer(user))
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture(autouse=True)
def without_embeddings(monkeypatch):
    """These tests are about persistence and files, not vectors. Skipping the embedding step keeps them fast
    (indexing runs at about 40 chunks/s); test_meaning_search_real.py covers vectors with the real model."""
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")


@pytest.fixture(autouse=True)
def clean_up(user_a, user_b):
    yield
    for user in (user_a, user_b):   # remove whatever a test left behind
        rest("DELETE", f"documents?user_id=eq.{user.id}", user)


# ------------------------------------------------------------------ authentication

def test_requests_without_valid_credentials_are_rejected(user_a):
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/documents", headers=bearer(user_a)).status_code == 200    # control
    tampered = user_a.token[:-4] + ("AAAA" if not user_a.token.endswith("AAAA") else "BBBB")
    assert client.get("/api/v1/documents", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    # The public project key is itself a token (or key) and must never count as a user.
    assert client.get("/api/v1/documents", headers={"Authorization": f"Bearer {KEY}"}).status_code == 401


def test_the_real_project_tokens_verify_with_the_published_key(user_a):
    from app.auth import get_verifier

    verified = get_verifier().verify(user_a.token)
    assert verified.id == user_a.id


# ------------------------------------------------------------------- persistence

def test_upload_query_and_delete_round_trip_through_the_database(user_a):
    doc = upload(user_a)
    assert re.fullmatch(r"[0-9a-f-]{36}", doc["id"]) and doc["status"] == "ready" and doc["chunk_count"] == 1

    listed = client.get("/api/v1/documents", headers=bearer(user_a)).json()["documents"]
    assert [d["id"] for d in listed] == [doc["id"]] and listed[0]["chunk_count"] == 1

    answer = client.post("/api/v1/queries", json=QUESTION, headers=bearer(user_a)).json()
    assert answer["evidence"][0]["document_id"] == doc["id"] and answer["evidence"][0]["page_number"] == 1

    # Ground truth straight from the database, as the user: the data really is persisted.
    row = rest("GET", f"documents?id=eq.{doc['id']}", user_a).json()[0]
    assert row["status"] == "ready" and row["user_id"] == user_a.id
    assert len(rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()) == 1

    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 404
    assert rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json() == []   # cascade


def test_a_second_app_instance_sees_the_same_data_because_nothing_lives_in_memory(user_a):
    doc = upload(user_a)
    fresh = TestClient(main.app)   # a "restart": new client, no shared state
    listed = fresh.get("/api/v1/documents", headers=bearer(user_a)).json()["documents"]
    assert [d["id"] for d in listed] == [doc["id"]]


# ---------------------------------------------------------------------- isolation

def test_another_user_gets_nothing_through_the_api(user_a, user_b):
    doc = upload(user_a)
    assert client.get("/api/v1/documents", headers=bearer(user_b)).json()["documents"] == []
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=bearer(user_b)).status_code == 404
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_b)).status_code == 404
    leak = client.post("/api/v1/queries", json={**QUESTION, "document_ids": [doc["id"]]}, headers=bearer(user_b))
    assert leak.status_code == 404
    assert client.post("/api/v1/queries", json=QUESTION, headers=bearer(user_b)).status_code == 409
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 200   # untouched


def test_the_document_limit_applies_per_user(user_a, user_b, monkeypatch):
    monkeypatch.setenv("MAX_DOCUMENTS", "1")
    upload(user_a, "1.txt")
    assert client.post("/api/v1/documents", files={"file": ("2.txt", b"two")}, headers=bearer(user_a)).status_code == 409
    upload(user_b, "1.txt")


# ------------------------------------------------------------------ failure paths

def test_a_failed_upload_leaves_nothing_behind(user_a, monkeypatch):
    def boom(self, document_id, chunks):
        raise RepositoryError(500)

    monkeypatch.setattr(SupabaseRepository, "add_chunks", boom)
    res = client.post("/api/v1/documents", files={"file": ("n.txt", TEXT)}, headers=bearer(user_a))
    assert res.status_code == 502
    assert rest("GET", "documents", user_a).json() == []   # the half-created row was removed


def test_binary_junk_and_nul_characters_do_not_break_storage(user_a):
    doc = upload(user_a, "weird.txt", b"before\x00after The Random Forest classifier \x00 selects difficulty")
    hit = client.post("/api/v1/queries", json=QUESTION, headers=bearer(user_a)).json()["evidence"][0]
    assert "\x00" not in hit["excerpt"] and hit["document_id"] == doc["id"]


# ------------------------------------------------------------------------ paging

def test_more_chunks_than_one_page_are_all_read_back(user_a):
    """The silent-truncation trap: a single request would stop at the server's row cap."""
    big = " ".join(f"word{i}" for i in range(210_000)).encode()          # about 1.4 MB of text
    doc = upload(user_a, "big.txt", big)
    assert doc["chunk_count"] > 1000
    repo = SupabaseRepository(AuthUser(user_a.id, user_a.token), base_url=URL, api_key=KEY)
    assert len(repo.search_chunks(None)) == doc["chunk_count"]
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).json()["chunk_count"] == doc["chunk_count"]
