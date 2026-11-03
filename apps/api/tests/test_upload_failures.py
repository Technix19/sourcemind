"""What happens when storage fails in the middle of an upload."""
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import AuthUser, current_user
from app.main import app
from app.repository import RepositoryError, get_repository
from conftest import AUTH_A, InMemoryRepository

client = TestClient(app, headers=AUTH_A)
FILE = {"file": ("notes.txt", b"The Random Forest classifier selects question difficulty.")}


def install_failure(backend, **failing):
    """Make chosen repository methods raise; the rest behave normally."""

    class Flaky(InMemoryRepository):
        pass

    for name, error in failing.items():
        def boom(self, *args, _error=error, **kwargs):
            raise _error
        setattr(Flaky, name, boom)

    def override(user: AuthUser = Depends(current_user)):
        return Flaky(backend, user.id)

    app.dependency_overrides[get_repository] = override


@pytest.mark.parametrize("step", ["add_chunks", "mark_ready"])
def test_failure_mid_upload_leaves_no_document_behind(fake_backend, step):
    install_failure(fake_backend, **{step: RepositoryError(500)})
    res = client.post("/api/v1/documents", files=FILE)
    assert res.status_code == 502
    assert fake_backend._docs, "the failing repository must have created a document first"
    assert all(not docs for docs in fake_backend._docs.values())   # ...and then rolled it back


def test_storage_errors_are_generic_and_never_leak_details(fake_backend):
    install_failure(fake_backend, add_chunks=RepositoryError(500))
    res = client.post("/api/v1/documents", files=FILE)
    assert res.status_code == 502
    assert res.json()["detail"] == "Storage is unavailable right now. Try again shortly."


def test_an_expired_session_during_storage_is_reported_as_401(fake_backend):
    install_failure(fake_backend, list_documents=RepositoryError(401))
    res = client.get("/api/v1/documents")
    assert res.status_code == 401 and "Sign in again" in res.json()["detail"]


def test_network_failure_to_storage_is_a_502(fake_backend):
    install_failure(fake_backend, count_documents=RepositoryError(None))
    assert client.post("/api/v1/documents", files=FILE).status_code == 502


def test_a_failed_cleanup_does_not_hide_the_original_error(fake_backend):
    install_failure(fake_backend, add_chunks=RepositoryError(500), delete_document=RepositoryError(500))
    assert client.post("/api/v1/documents", files=FILE).status_code == 502


def test_invalid_files_never_touch_storage(fake_backend):
    install_failure(fake_backend, count_documents=RepositoryError(500), create_document=RepositoryError(500))
    assert client.post("/api/v1/documents", files={"file": ("x.exe", b"MZ")}).status_code == 400
    assert client.post("/api/v1/documents", files={"file": ("e.txt", b"   ")}).status_code == 422
