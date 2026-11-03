"""SupabaseRepository against a fake HTTP server (no network). These tests pin down what we send."""
import json

import httpx
import pytest

from app.auth import AuthUser
from app.ingestion import PageChunk
from app.repository import INSERT_BATCH, PAGE_SIZE, RepositoryError, SupabaseRepository

BASE, KEY = "https://proj.supabase.co", "public-key"
DOC_A = "11111111-1111-1111-1111-111111111111"
DOC_B = "22222222-2222-2222-2222-222222222222"


class FakeServer:
    """Records requests; answers from a handler. Can cap page sizes like a real PostgREST."""

    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def repo(server: FakeServer, token="token-a") -> SupabaseRepository:
    return SupabaseRepository(AuthUser("u", token), base_url=BASE, api_key=KEY, http=server.client())


def paged_table(rows, server_cap=None):
    """Behaves like PostgREST: honours limit/offset, optionally caps the page, sends Content-Range."""
    def handler(request):
        q = request.url.params
        limit, offset = int(q["limit"]), int(q["offset"])
        if server_cap:
            limit = min(limit, server_cap)
        page = rows[offset : offset + limit]
        end = offset + len(page) - 1 if page else offset
        return httpx.Response(200, json=page, headers={"Content-Range": f"{offset}-{end}/{len(rows)}"})
    return handler


def test_every_request_carries_the_callers_own_token_and_the_public_key():
    server = FakeServer(lambda r: httpx.Response(200, json=[], headers={"Content-Range": "*/0"}))
    repo(server, "token-a").list_documents()
    repo(server, "token-b").list_documents()
    auth = [r.headers["authorization"] for r in server.requests]
    assert auth == ["Bearer token-a", "Bearer token-b"]
    assert all(r.headers["apikey"] == KEY for r in server.requests)


def test_a_shared_connection_pool_never_leaks_identity_between_repositories():
    server = FakeServer(lambda r: httpx.Response(200, json=[], headers={"Content-Range": "*/0"}))
    shared = server.client()
    a = SupabaseRepository(AuthUser("a", "token-a"), base_url=BASE, api_key=KEY, http=shared)
    b = SupabaseRepository(AuthUser("b", "token-b"), base_url=BASE, api_key=KEY, http=shared)
    a.list_documents(); b.list_documents(); a.list_documents()
    assert [r.headers["authorization"] for r in server.requests] == ["Bearer token-a", "Bearer token-b", "Bearer token-a"]


def test_reading_follows_pages_until_everything_is_fetched():
    rows = [{"id": f"{i:036d}", "name": "n", "size_bytes": 1, "page_count": 1, "status": "ready"} for i in range(2300)]
    server = FakeServer(paged_table(rows))
    assert len(repo(server).list_documents()) == 2300
    assert len(server.requests) == 3                       # 1000 + 1000 + 300


def test_a_server_row_cap_lower_than_our_page_size_does_not_truncate_results():
    """The silent-truncation trap: the server returns 500 per page although we asked for 1000."""
    rows = [{"id": f"{i:036d}", "name": "n", "size_bytes": 1, "page_count": 1, "status": "ready"} for i in range(1200)]
    server = FakeServer(paged_table(rows, server_cap=500))
    assert PAGE_SIZE > 500
    assert len(repo(server).list_documents()) == 1200


def test_empty_results_stop_cleanly():
    server = FakeServer(paged_table([]))
    assert repo(server).list_documents() == [] and len(server.requests) == 1


def test_invalid_ids_never_reach_the_database():
    server = FakeServer(lambda r: httpx.Response(200, json=[]))
    r = repo(server)
    for evil in ["not-a-uuid", "x,y", "1) or (1=1", "../documents", ""]:
        assert r.get_document(evil) is None
        assert r.delete_document(evil) is False
        assert r.search_chunks([DOC_A, evil]) is None
    assert server.requests == []


def test_uuid_input_is_canonicalised_before_use_in_filters():
    server = FakeServer(lambda r: httpx.Response(200, json=[]))
    repo(server).get_document(DOC_A.replace("-", "").upper())
    assert server.requests[0].url.params["id"] == f"eq.{DOC_A}"


def test_search_returns_none_when_a_requested_document_is_not_the_callers():
    docs = [{"id": DOC_A, "name": "a.pdf"}]                 # B's document is invisible to this user (RLS)
    server = FakeServer(paged_table(docs))
    assert repo(server).search_chunks([DOC_A, DOC_B]) is None


def test_search_orders_chunks_by_document_then_page_then_index_and_names_them():
    def handler(request):
        if request.url.path.endswith("/documents"):
            return paged_table([{"id": DOC_A, "name": "a.pdf"}, {"id": DOC_B, "name": "b.pdf"}])(request)
        rows = [
            {"document_id": DOC_B, "page_number": 1, "chunk_index": 0, "text": "b1"},
            {"document_id": DOC_A, "page_number": 2, "chunk_index": 0, "text": "a2"},
            {"document_id": DOC_A, "page_number": 1, "chunk_index": 1, "text": "a1b"},
            {"document_id": DOC_A, "page_number": 1, "chunk_index": 0, "text": "a1a"},
        ]
        return paged_table(rows)(request)

    out = repo(FakeServer(handler)).search_chunks(None)
    assert [c.text for c in out] == ["a1a", "a1b", "a2", "b1"]
    assert out[0].filename == "a.pdf" and out[0].chunk_id == f"{DOC_A}-p1-c0"


def test_search_with_no_ready_documents_makes_no_chunk_request():
    server = FakeServer(paged_table([]))
    assert repo(server).search_chunks(None) == []
    assert len(server.requests) == 1


def test_new_documents_start_as_indexing_and_the_client_never_names_an_owner():
    server = FakeServer(lambda r: httpx.Response(201, json=[{"id": DOC_A, "name": "a", "size_bytes": 5, "page_count": 1, "status": "indexing"}]))
    repo(server).create_document("a", 5, 1)
    body = json.loads(server.requests[0].content)
    assert body["status"] == "indexing" and "user_id" not in body


def test_chunks_are_inserted_in_batches_without_an_owner_field():
    server = FakeServer(lambda r: httpx.Response(201))
    chunks = [PageChunk(1, i, 0, 5, "hello") for i in range(INSERT_BATCH * 2 + 50)]
    repo(server).add_chunks(DOC_A, chunks)
    sizes = [len(json.loads(r.content)) for r in server.requests]
    assert sizes == [INSERT_BATCH, INSERT_BATCH, 50]
    assert all("user_id" not in row for r in server.requests for row in json.loads(r.content))
    assert all(r.headers["prefer"] == "return=minimal" for r in server.requests)


def test_upstream_failures_become_repository_errors_with_a_status():
    for status, unauthorized in [(401, True), (403, True), (500, False), (409, False)]:
        server = FakeServer(lambda r, s=status: httpx.Response(s, json={"message": "secret internal detail"}))
        with pytest.raises(RepositoryError) as caught:
            repo(server).list_documents()
        assert caught.value.status == status and caught.value.unauthorized is unauthorized
        assert "secret" not in str(caught.value)             # upstream details never propagate


def test_network_failure_is_a_repository_error_without_a_status():
    def boom(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(RepositoryError) as caught:
        repo(FakeServer(boom)).list_documents()
    assert caught.value.status is None
