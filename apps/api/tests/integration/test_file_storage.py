"""Private file storage against the REAL Supabase project (needs migration 20261103000002).

Real tokens, a real private bucket, two real users. Signed links are bearer credentials, so
these tests check who can CREATE one, who can read without one, and that links expire.
"""
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthUser
from app.repository import BUCKET, RepositoryError, SupabaseRepository
from conftest import make_pdf
from supabase_helpers import KEY, URL, rest, skip_without_supabase, user_a, user_b  # noqa: F401

pytestmark = [pytest.mark.integration, skip_without_supabase]

client = TestClient(main.app)
PDF = make_pdf(["Introduction to extraction", "The Random Forest classifier selects difficulty"])
SETUP_HINT = "Storage is not set up: apply supabase/migrations/20261103000002_private_storage.sql (see docs/m6c-apply.md)."


def bearer(user):
    return {"Authorization": f"Bearer {user.token}"}


def repo_for(user) -> SupabaseRepository:
    return SupabaseRepository(AuthUser(user.id, user.token), base_url=URL, api_key=KEY)


def upload(user, name="paper.pdf", data=PDF):
    res = client.post("/api/v1/documents", files={"file": (name, data)}, headers=bearer(user))
    assert res.status_code == 201, f"{SETUP_HINT} Upload said {res.status_code}: {res.text}"
    return res.json()


def storage(method, path, user=None, **kwargs):
    headers = {"apikey": KEY, **({"Authorization": f"Bearer {user.token}"} if user else {})}
    headers.update(kwargs.pop("headers", {}))
    return httpx.request(method, f"{URL}/storage/v1/{path}", headers=headers, timeout=30, **kwargs)


@pytest.fixture(autouse=True)
def without_embeddings(monkeypatch):
    """These tests are about persistence and files, not vectors. Skipping the embedding step keeps them fast
    (indexing runs at about 40 chunks/s); test_meaning_search_real.py covers vectors with the real model."""
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")


@pytest.fixture(autouse=True)
def clean_up(user_a, user_b):
    yield
    for user in (user_a, user_b):
        client.get("/api/v1/documents", headers=bearer(user))                       # runs any pending deletion sweep
        for doc in client.get("/api/v1/documents", headers=bearer(user)).json().get("documents", []):
            client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user))
        rest("DELETE", f"documents?user_id=eq.{user.id}", user)


# ------------------------------------------------------------------ upload + signed link

def test_storage_is_set_up_and_an_upload_stores_the_original_file(user_a):
    doc = upload(user_a)
    assert doc["has_file"] is True
    link = client.get(f"/api/v1/documents/{doc['id']}/view", params={"page": 2}, headers=bearer(user_a))
    assert link.status_code == 200, link.text
    body = link.json()
    assert body["expires_in"] == 60 and link.headers["cache-control"] == "no-store"
    fetched = httpx.get(body["url"], timeout=30)                  # the link itself needs no other credential
    assert fetched.status_code == 200 and fetched.content == PDF
    assert fetched.headers["content-type"].startswith("application/pdf")


def test_text_files_are_served_as_plain_text(user_a):
    doc = upload(user_a, "notes.txt", b"The Random Forest classifier selects difficulty.")
    url = client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).json()["url"]
    fetched = httpx.get(url, timeout=30)
    assert fetched.status_code == 200 and fetched.headers["content-type"].startswith("text/plain")


def test_a_signed_link_stops_working_after_it_expires(user_a):
    doc = upload(user_a)
    url = repo_for(user_a).signed_url(doc["id"], expires_in=2)
    assert httpx.get(url, timeout=30).status_code == 200
    time.sleep(3.5)
    assert httpx.get(url, timeout=30).status_code != 200


# ------------------------------------------------------------------ nobody else gets in

def test_the_bucket_is_private_so_public_urls_do_not_work(user_a):
    doc = upload(user_a)
    key = f"{user_a.id}/{doc['id']}"
    for path in (f"object/public/{BUCKET}/{key}", f"object/{BUCKET}/{key}"):
        res = storage("GET", path)                                # no credentials at all
        assert res.status_code != 200 and res.content != PDF


def test_another_user_cannot_get_a_link_or_read_the_file(user_a, user_b):
    doc = upload(user_a)
    key = f"{user_a.id}/{doc['id']}"
    assert client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_b)).status_code == 404
    stolen = storage("POST", f"object/sign/{BUCKET}/{key}", user_b, json={"expiresIn": 60})   # bypass our API
    assert stolen.status_code != 200 and "signedURL" not in stolen.text
    direct = storage("GET", f"object/authenticated/{BUCKET}/{key}", user_b)
    assert direct.status_code != 200 and direct.content != PDF
    assert client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).status_code == 200   # control


def test_users_cannot_write_into_someone_elses_folder_or_create_orphans(user_a, user_b):
    doc = upload(user_a)
    other = str(uuid.uuid4())
    assert storage("POST", f"object/{BUCKET}/{user_a.id}/{other}", user_b, content=b"x", headers={"Content-Type": "text/plain"}).status_code >= 400
    # Even in your OWN folder, a file with no document row that points at it is refused.
    assert storage("POST", f"object/{BUCKET}/{user_b.id}/{other}", user_b, content=b"x", headers={"Content-Type": "text/plain"}).status_code >= 400
    assert storage("POST", f"object/{BUCKET}/{user_a.id}/{other}", None, content=b"x", headers={"Content-Type": "text/plain"}).status_code >= 400
    assert client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).status_code == 200


def test_another_user_cannot_delete_my_file(user_a, user_b):
    doc = upload(user_a)
    key = f"{user_a.id}/{doc['id']}"
    storage("DELETE", f"object/{BUCKET}/{key}", user_b)
    url = client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).json()["url"]
    assert httpx.get(url, timeout=30).content == PDF              # still there


def test_a_stored_file_cannot_be_overwritten(user_a):
    doc = upload(user_a)
    with pytest.raises(RepositoryError):
        repo_for(user_a).put_file(doc["id"], b"%PDF-evil", "application/pdf")
    url = client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).json()["url"]
    assert httpx.get(url, timeout=30).content == PDF


def test_the_bucket_itself_enforces_type_and_size_limits(user_a):
    repo = repo_for(user_a)
    doc = repo.create_document("x.pdf", 1, 1)                      # a row, so the policy would allow the upload
    with pytest.raises(RepositoryError):
        repo.put_file(doc.id, b"<html><script>1</script></html>", "text/html")
    with pytest.raises(RepositoryError):
        repo.put_file(doc.id, b"%PDF" + b"0" * (12 * 1024 * 1024), "application/pdf")   # 12 MB + a little
    repo.delete_document(doc.id)


# ------------------------------------------------------------------------- deletion

def test_deleting_removes_the_file_the_chunks_and_the_row(user_a):
    doc = upload(user_a)
    url = client.get(f"/api/v1/documents/{doc['id']}/view", headers=bearer(user_a)).json()["url"]
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 204
    assert rest("GET", f"documents?id=eq.{doc['id']}", user_a).json() == []
    assert rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json() == []
    assert repo_for(user_a).signed_url(doc["id"]) is None
    # A link that was never fetched is dead at once. (One that WAS fetched is cached at the CDN
    # until its own expiry; see the next test.)
    assert httpx.get(url, timeout=30).status_code != 200


def test_a_link_that_was_already_used_cannot_outlive_its_expiry_even_after_deletion(user_a):
    """Measured platform behavior: the CDN keeps a fetched file for the rest of that link's life, so
    deleting a document does NOT revoke a link someone has already used. The cached copy still dies
    with the link's own expiry, and THAT bound (60 s in the app) is what the design relies on."""
    doc = upload(user_a)
    url = repo_for(user_a).signed_url(doc["id"], expires_in=4)
    assert httpx.get(url, timeout=30).status_code == 200             # now cached at the edge
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 204
    time.sleep(5.5)                                                  # past the link's own expiry
    assert httpx.get(url, timeout=30).status_code != 200


def test_an_interrupted_deletion_hides_the_document_and_is_finished_automatically(user_a, monkeypatch):
    doc = upload(user_a)
    real_storage = SupabaseRepository._storage

    def failing_storage(self, method, path, **kwargs):
        if method == "DELETE":
            raise RepositoryError(500)                              # the file delete "crashes"
        return real_storage(self, method, path, **kwargs)

    monkeypatch.setattr(SupabaseRepository, "_storage", failing_storage)
    res = client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a))
    assert res.status_code == 502 and "cleaned up automatically" in res.json()["detail"]
    monkeypatch.undo()

    row = rest("GET", f"documents?id=eq.{doc['id']}", user_a).json()[0]
    assert row["status"] == "deleting"                              # hidden, not half-alive
    assert rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json() == []   # text already unsearchable
    answer = client.post("/api/v1/queries", json={"question": "Which classifier selects difficulty?"}, headers=bearer(user_a))
    assert answer.status_code == 409                                # nothing searchable remains

    listed = client.get("/api/v1/documents", headers=bearer(user_a))   # opening the app resumes the cleanup
    assert listed.status_code == 200 and listed.json()["documents"] == []
    assert rest("GET", f"documents?id=eq.{doc['id']}", user_a).json() == []
    assert repo_for(user_a).signed_url(doc["id"]) is None


def test_a_document_stored_before_file_storage_existed_reports_no_file(user_a):
    made = rest("POST", "documents", user_a, json={"name": "old.pdf", "size_bytes": 5, "page_count": 1})   # no storage_key
    assert made.status_code == 201
    doc_id = made.json()[0]["id"]
    listed = client.get("/api/v1/documents", headers=bearer(user_a)).json()["documents"]
    assert [d for d in listed if d["id"] == doc_id][0]["has_file"] is False
    res = client.get(f"/api/v1/documents/{doc_id}/view", headers=bearer(user_a))
    assert res.status_code == 404 and "Upload it again" in res.json()["detail"]


# ------------------------------------------------------------------ abandoned uploads

def _crashed_upload(user, name="crashed.pdf"):
    """What a server crash mid-upload leaves behind: a row in `indexing`, its file and its chunks."""
    from app.ingestion import PageChunk
    repo = repo_for(user)
    doc = repo.create_document(name, len(PDF), 1)
    repo.put_file(doc.id, PDF, "application/pdf")
    repo.add_chunks(doc.id, [PageChunk(page_number=1, chunk_index=0, start=0, end=17, text="half indexed text")])
    return doc


def test_an_abandoned_upload_is_removed_with_its_file_and_chunks_but_a_fresh_one_is_not(user_a):
    doc = _crashed_upload(user_a)
    assert repo_for(user_a).remove_abandoned_uploads(900) == 0              # only seconds old: may still be running
    assert rest("GET", f"documents?id=eq.{doc.id}", user_a).json()[0]["status"] == "indexing"

    time.sleep(2.2)                                                         # the cutoff has one-second resolution
    assert repo_for(user_a).remove_abandoned_uploads(1) == 1
    assert rest("GET", f"documents?id=eq.{doc.id}", user_a).json() == []
    assert rest("GET", f"chunks?document_id=eq.{doc.id}", user_a).json() == []
    assert repo_for(user_a).signed_url(doc.id) is None


def test_the_sweep_never_touches_another_users_stuck_upload_or_a_ready_document(user_a, user_b):
    mine, theirs = _crashed_upload(user_a), _crashed_upload(user_b)
    ready = upload(user_a)
    time.sleep(2.2)
    assert repo_for(user_a).remove_abandoned_uploads(1) == 1                # only mine
    assert rest("GET", f"documents?id=eq.{mine.id}", user_a).json() == []
    assert rest("GET", f"documents?id=eq.{theirs.id}", user_b).json()[0]["status"] == "indexing"
    assert rest("GET", f"documents?id=eq.{ready['id']}", user_a).json()[0]["status"] == "ready"


def test_opening_the_library_cleans_up_an_abandoned_upload(user_a, monkeypatch):
    import dataclasses
    real = main.get_settings
    monkeypatch.setattr(main, "get_settings", lambda: dataclasses.replace(real(), stale_upload_seconds=1))
    doc = _crashed_upload(user_a)
    time.sleep(2.2)
    listed = client.get("/api/v1/documents", headers=bearer(user_a))
    assert listed.status_code == 200 and listed.json()["documents"] == []
    assert rest("GET", f"documents?id=eq.{doc.id}", user_a).json() == []
