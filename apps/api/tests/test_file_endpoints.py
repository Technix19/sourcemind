"""Stored original files through the API: upload, 'view' links, delete."""
import logging

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import AuthUser, current_user
from app.main import app
from app.repository import RepositoryError, get_repository
from conftest import AUTH_A, AUTH_B, USER_A, InMemoryRepository, make_pdf

alice = TestClient(app, headers=AUTH_A)
bob = TestClient(app, headers=AUTH_B)
PDF = make_pdf(["Introduction to extraction", "The Random Forest classifier selects difficulty"])


def upload(client, name="paper.pdf", data=PDF, mime="application/octet-stream"):
    res = client.post("/api/v1/documents", files={"file": (name, data, mime)})
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------------------------------------------ what gets stored

def test_the_original_bytes_are_stored_with_a_content_type_we_choose(fake_backend):
    doc = upload(alice)
    data, content_type = fake_backend.files[(USER_A.id, doc["id"])]
    assert data == PDF and content_type == "application/pdf" and doc["has_file"] is True


@pytest.mark.parametrize("name,expected", [("notes.txt", "text/plain"), ("readme.md", "text/plain"), ("DOC.PDF", "application/pdf")])
def test_text_and_markdown_are_stored_as_plain_text_never_as_something_active(fake_backend, name, expected):
    data = PDF if name.upper().endswith("PDF") else b"# Title\n\nSome text about classifiers."
    doc = upload(alice, name, data)
    assert fake_backend.files[(USER_A.id, doc["id"])][1] == expected


def test_a_client_claiming_a_dangerous_content_type_changes_nothing(fake_backend):
    doc = upload(alice, "page.txt", b"<script>alert(1)</script> classifier", mime="text/html")
    assert fake_backend.files[(USER_A.id, doc["id"])][1] == "text/plain"


def test_responses_never_reveal_where_a_file_is_stored(fake_backend):
    doc = upload(alice)
    text = alice.get("/api/v1/documents").text + alice.get(f"/api/v1/documents/{doc['id']}").text
    assert "storage" not in text.lower() and USER_A.id not in text


# ------------------------------------------------------------------------ view links

def test_view_returns_a_short_lived_link_that_is_never_cached(fake_backend):
    doc = upload(alice)
    res = alice.get(f"/api/v1/documents/{doc['id']}/view", params={"page": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["url"].startswith("https://files.test/") and body["expires_in"] == 60
    assert body["page"] == 2 and body["filename"] == "paper.pdf"
    assert res.headers["cache-control"] == "no-store"


def test_view_without_a_page_is_allowed():
    doc = upload(alice)
    assert alice.get(f"/api/v1/documents/{doc['id']}/view").json()["page"] is None


@pytest.mark.parametrize("page,status", [(0, 422), (-1, 422), (3, 422), ("x", 422), (2, 200), (1, 200)])
def test_view_validates_the_page_number(page, status):
    doc = upload(alice)   # a 2-page PDF
    assert alice.get(f"/api/v1/documents/{doc['id']}/view", params={"page": page}).status_code == status


def test_another_user_cannot_get_a_link_to_my_file():
    doc = upload(alice)
    assert bob.get(f"/api/v1/documents/{doc['id']}/view").status_code == 404
    assert alice.get(f"/api/v1/documents/{doc['id']}/view").status_code == 200


def test_an_unknown_or_malformed_id_is_404():
    assert alice.get("/api/v1/documents/not-a-uuid/view").status_code == 404
    assert alice.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/view").status_code == 404


def test_older_documents_without_a_stored_file_get_a_clear_message(fake_backend):
    doc = upload(alice)
    fake_backend.files.clear()                       # simulate a document uploaded before file storage
    import dataclasses
    repo = fake_backend.repo_for(USER_A)
    repo._docs[doc["id"]] = dataclasses.replace(repo._docs[doc["id"]], has_file=False)
    res = alice.get(f"/api/v1/documents/{doc['id']}/view")
    assert res.status_code == 404 and "Upload it again" in res.json()["detail"]
    assert alice.get(f"/api/v1/documents/{doc['id']}").json()["has_file"] is False


def test_the_signed_link_is_never_written_to_the_logs(caplog):
    doc = upload(alice)
    with caplog.at_level(logging.DEBUG):
        link = alice.get(f"/api/v1/documents/{doc['id']}/view").json()["url"]
    assert link not in caplog.text and "token=" not in caplog.text


# --------------------------------------------------------------------------- failures

def install(backend, **failing):
    class Flaky(InMemoryRepository):
        pass

    for name, error in failing.items():
        setattr(Flaky, name, lambda self, *a, _e=error, **k: (_ for _ in ()).throw(_e))

    def override(user: AuthUser = Depends(current_user)):
        return Flaky(backend, user.id)

    app.dependency_overrides[get_repository] = override


@pytest.mark.parametrize("failing_step", ["put_file", "add_chunks", "mark_ready"])
def test_a_failed_upload_leaves_no_document_and_no_file(fake_backend, failing_step):
    install(fake_backend, **{failing_step: RepositoryError(500)})
    res = alice.post("/api/v1/documents", files={"file": ("paper.pdf", PDF)})
    assert res.status_code == 502
    assert fake_backend.files == {}                                   # the file was removed too
    assert all(not docs for docs in fake_backend._docs.values())      # and the row


def test_deleting_removes_the_file_as_well(fake_backend):
    doc = upload(alice)
    assert fake_backend.files
    assert alice.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert fake_backend.files == {}
    assert alice.get(f"/api/v1/documents/{doc['id']}/view").status_code == 404


def test_a_delete_that_cannot_finish_says_it_will_be_cleaned_up_and_leaks_nothing(fake_backend):
    install(fake_backend, delete_document=RepositoryError(500))
    res = alice.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 502 and "cleaned up automatically" in res.json()["detail"]


def test_listing_resumes_interrupted_deletions_and_survives_their_failure(fake_backend):
    calls = []

    class Sweeping(InMemoryRepository):
        def finish_pending_deletions(self):
            calls.append(1)
            return 1

    app.dependency_overrides[get_repository] = lambda user=Depends(current_user): Sweeping(fake_backend, user.id)
    assert alice.get("/api/v1/documents").status_code == 200 and calls == [1]

    install(fake_backend, finish_pending_deletions=RepositoryError(500))
    assert alice.get("/api/v1/documents").status_code == 200          # a failed sweep never breaks listing
