"""Original-file storage, signed links and recoverable deletion, against a fake Supabase (no network)."""
import json

import httpx
import pytest

from app.auth import AuthUser
from app.repository import BUCKET, RepositoryError, SupabaseRepository, valid_id

BASE, KEY, UID = "https://proj.supabase.co", "public-key", "11111111-1111-1111-1111-111111111111"
DOC = "22222222-2222-2222-2222-222222222222"


class FakeSupabase:
    """Just enough of PostgREST + Storage, with state, and a way to make one step fail."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.chunks: dict[str, int] = {}
        self.objects: dict[str, bytes] = {}
        self.calls: list[str] = []
        self.fail: set[str] = set()
        self.requests: list[httpx.Request] = []

    def add_document(self, doc_id=DOC, status="ready", stored=True, chunks=3):
        key = f"{UID}/{doc_id}"
        self.docs[doc_id] = {"id": doc_id, "status": status, "storage_key": key if stored else None, "name": "a.pdf",
                             "size_bytes": 5, "page_count": 2}
        self.chunks[doc_id] = chunks
        if stored:
            self.objects[key] = b"%PDF-data"

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))

    def _row_filter(self, request):
        q = request.url.params
        rows = list(self.docs.values())
        if "id" in q:
            rows = [r for r in rows if f"eq.{r['id']}" == q["id"]]
        if "status" in q:
            op, _, value = q["status"].partition(".")
            rows = [r for r in rows if (r["status"] == value) == (op == "eq")]
        return rows

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, method = request.url.path, request.method
        step = None
        if path.endswith("/rest/v1/documents"):
            step = {"GET": "read", "PATCH": "mark", "DELETE": "row"}.get(method)
        elif path.endswith("/rest/v1/chunks"):
            step = "chunks"
        elif "/storage/v1/object/" in path and method == "DELETE":
            step = "object"
        elif "/storage/v1/object/sign/" in path:
            step = "sign"
        if step:
            self.calls.append(step)
        if step in self.fail:
            return httpx.Response(500, json={"message": "boom internal detail"})

        if step == "read":
            rows = self._row_filter(request)
            return httpx.Response(200, json=rows, headers={"Content-Range": f"0-{max(len(rows) - 1, 0)}/{len(rows)}"})
        if step == "mark":
            for r in self._row_filter(request):
                r.update(json.loads(request.content))
            return httpx.Response(204)
        if step == "chunks":
            self.chunks[request.url.params["document_id"].removeprefix("eq.")] = 0
            return httpx.Response(204)
        if step == "object":
            key = path.split(f"/object/{BUCKET}/", 1)[1]
            if key not in self.objects:   # the real service answers HTTP 400 with statusCode "404"
                return httpx.Response(400, json={"statusCode": "404", "error": "not_found"})
            del self.objects[key]
            return httpx.Response(200, json={"message": "Successfully deleted"})
        if step == "row":
            for r in self._row_filter(request):
                del self.docs[r["id"]]
            return httpx.Response(204)
        if step == "sign":
            key = path.split(f"/object/sign/{BUCKET}/", 1)[1]
            if key not in self.objects:
                return httpx.Response(400, json={"statusCode": "404"})
            return httpx.Response(200, json={"signedURL": f"/object/sign/{BUCKET}/{key}?token=abc"})
        return httpx.Response(200, json=[])


@pytest.fixture
def server():
    return FakeSupabase()


def repo(server, token="token-a"):
    return SupabaseRepository(AuthUser(UID, token), base_url=BASE, api_key=KEY, http=server.client())


# ------------------------------------------------------------------ creating + uploading

def test_a_new_document_row_names_its_own_storage_key_from_ids_only():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{**seen["body"]}])

    fake = httpx.Client(transport=httpx.MockTransport(handler))
    doc = SupabaseRepository(AuthUser(UID, "t"), base_url=BASE, api_key=KEY, http=fake).create_document("My Secret Report.pdf", 5, 1)
    body = seen["body"]
    assert body["storage_key"] == f"{UID}/{body['id']}"          # ids only: never the user's filename
    assert "Secret" not in body["storage_key"] and "user_id" not in body
    assert doc.has_file is True


def test_the_file_is_uploaded_under_the_users_own_path_without_overwriting(server):
    repo(server).put_file(DOC, b"%PDF-bytes", "application/pdf")
    request = server.requests[0]
    assert request.method == "POST" and request.url.path == f"/storage/v1/object/{BUCKET}/{UID}/{DOC}"
    assert request.content == b"%PDF-bytes"
    assert request.headers["content-type"] == "application/pdf"
    assert request.headers["x-upsert"] == "false"                 # stored files are immutable
    assert request.headers["authorization"] == "Bearer token-a" and request.headers["apikey"] == KEY


def test_an_invalid_document_id_never_reaches_storage(server):
    with pytest.raises(RepositoryError):
        repo(server).put_file("../../etc/passwd", b"x", "text/plain")
    assert repo(server).signed_url("a/b") is None
    assert server.requests == []


def test_a_rejected_upload_is_an_error_not_silent():
    class Rejecting(FakeSupabase):
        def __call__(self, request):
            return httpx.Response(403, json={"message": "row-level security"})

    with pytest.raises(RepositoryError) as caught:
        repo(Rejecting()).put_file(DOC, b"x", "text/plain")
    assert caught.value.status == 403 and caught.value.unauthorized


# ------------------------------------------------------------------------- signed links

def test_a_signed_link_is_absolute_short_lived_and_requested_with_the_users_token(server):
    server.add_document()
    url = repo(server).signed_url(DOC)
    assert url == f"{BASE}/storage/v1/object/sign/{BUCKET}/{UID}/{DOC}?token=abc"
    request = server.requests[0]
    assert json.loads(request.content) == {"expiresIn": 60}
    assert request.headers["authorization"] == "Bearer token-a"


def test_the_link_lifetime_can_be_chosen_per_call(server):
    server.add_document()
    repo(server).signed_url(DOC, expires_in=2)
    assert json.loads(server.requests[0].content) == {"expiresIn": 2}


@pytest.mark.parametrize("returned", [f"/object/sign/{BUCKET}/x?token=1", f"/storage/v1/object/sign/{BUCKET}/x?token=1"])
def test_both_shapes_of_signed_path_become_the_same_absolute_url(returned):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"signedURL": returned})))
    url = SupabaseRepository(AuthUser(UID, "t"), base_url=BASE, api_key=KEY, http=client).signed_url(DOC)
    assert url == f"{BASE}/storage/v1/object/sign/{BUCKET}/x?token=1"


@pytest.mark.parametrize("returned", ["https://evil.example/steal", "//evil.example/x", f"/storage/v1/object/public/{BUCKET}/x", ""])
def test_a_link_that_does_not_point_at_our_private_bucket_is_refused(returned):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"signedURL": returned})))
    assert SupabaseRepository(AuthUser(UID, "t"), base_url=BASE, api_key=KEY, http=client).signed_url(DOC) is None


def test_a_missing_file_gives_no_link_but_a_real_failure_raises(server):
    assert repo(server).signed_url(DOC) is None            # the real service says HTTP 400 / statusCode 404
    server.add_document()
    server.fail.add("sign")
    with pytest.raises(RepositoryError):
        repo(server).signed_url(DOC)


# ------------------------------------------------------------------ recoverable deletion

def test_deletion_runs_in_the_safe_order(server):
    server.add_document()
    assert repo(server).delete_document(DOC) is True
    assert server.calls == ["read", "mark", "chunks", "object", "row"]
    assert server.docs == {} and server.objects == {} and server.chunks[DOC] == 0


@pytest.mark.parametrize("failing", ["mark", "chunks", "object", "row"])
def test_a_crash_at_any_step_is_finished_by_trying_again(server, failing):
    server.add_document()
    server.fail.add(failing)
    with pytest.raises(RepositoryError):
        repo(server).delete_document(DOC)
    # Whatever happened, the document is no longer usable: it is hidden, or already gone.
    if failing != "mark":
        assert server.docs[DOC]["status"] == "deleting"
    server.fail.clear()
    assert repo(server).finish_pending_deletions() == (0 if failing == "mark" else 1)
    if failing == "mark":                       # nothing was started, so nothing is pending: delete again
        assert repo(server).delete_document(DOC) is True
    assert server.docs == {} and server.objects == {} and server.chunks[DOC] == 0


def test_the_content_is_unsearchable_before_the_file_is_touched(server):
    server.add_document()
    server.fail.add("object")                   # the file delete fails after the chunks are gone
    with pytest.raises(RepositoryError):
        repo(server).delete_document(DOC)
    assert server.chunks[DOC] == 0              # text already removed
    assert server.docs[DOC]["status"] == "deleting"            # hidden from lists and search
    assert repo(server).get_document(DOC) is None
    assert repo(server).list_documents() == []


def test_a_missing_file_does_not_block_deleting_the_row(server):
    server.add_document(stored=True)
    server.objects.clear()                      # the file vanished earlier
    assert repo(server).delete_document(DOC) is True
    assert server.docs == {}


def test_documents_without_a_stored_file_skip_the_storage_step(server):
    server.add_document(stored=False)
    assert repo(server).delete_document(DOC) is True
    assert "object" not in server.calls


def test_deleting_something_that_is_not_there_is_false_and_touches_nothing(server):
    assert repo(server).delete_document(DOC) is False
    assert server.calls == ["read"]
    assert repo(server).delete_document("not-a-uuid") is False


def test_sweep_finishes_only_documents_already_marked_deleting(server):
    other = "33333333-3333-3333-3333-333333333333"
    server.add_document(DOC, status="deleting")
    server.add_document(other, status="ready")
    assert repo(server).finish_pending_deletions() == 1
    assert set(server.docs) == {other} and f"{UID}/{other}" in server.objects


def test_resuming_does_not_mark_again(server):
    server.add_document(status="deleting")
    repo(server).delete_document(DOC)
    assert "mark" not in server.calls


def test_upstream_error_details_never_propagate(server):
    server.add_document()
    server.fail.add("chunks")
    with pytest.raises(RepositoryError) as caught:
        repo(server).delete_document(DOC)
    assert "boom" not in str(caught.value)


def test_the_summary_says_whether_a_file_exists_but_never_where(server):
    from app.repository import Document

    summary = Document(DOC, "a", 1, 1, "ready", 1, True).summary()
    assert summary["has_file"] is True and not any("key" in k or "path" in k for k in summary)
    assert valid_id(DOC) == DOC
