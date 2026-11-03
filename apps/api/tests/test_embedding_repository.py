"""Vector storage and search through the repository, against a fake HTTP server."""
import json

import httpx
import pytest

from app.auth import AuthUser
from app.embeddings import DIMENSION
from app.ingestion import PageChunk
from app.repository import EMBED_BATCH, INSERT_BATCH, RepositoryError, SupabaseRepository

BASE, KEY, UID = "https://proj.supabase.co", "public-key", "11111111-1111-1111-1111-111111111111"
DOC_A, DOC_B = "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"
MODEL = "BAAI/bge-small-en-v1.5"
VEC = [0.25] * DIMENSION


class Server:
    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def __call__(self, request):
        self.requests.append(request)
        return self._handler(request)

    def repo(self, token="token-a", model=MODEL):
        client = httpx.Client(transport=httpx.MockTransport(self))
        return SupabaseRepository(AuthUser(UID, token), base_url=BASE, api_key=KEY, http=client, embedding_model=model)


def doc_rows(*docs):
    def handler(request):
        if request.url.path.endswith("/documents"):
            return httpx.Response(200, json=list(docs), headers={"Content-Range": f"0-{len(docs) - 1}/{len(docs)}"})
        if request.url.path.endswith("/rpc/match_chunks"):
            return httpx.Response(200, json=[
                {"document_id": DOC_A, "page_number": 2, "chunk_index": 0, "text": "best", "similarity": 0.91},
                {"document_id": DOC_A, "page_number": 1, "chunk_index": 3, "text": "next", "similarity": 0.62},
            ])
        return httpx.Response(200, json=[])
    return handler


def test_chunks_get_their_ids_from_us_so_vectors_can_reference_them():
    server = Server(lambda r: httpx.Response(201))
    chunks = [PageChunk(1, i, 0, 5, "hello") for i in range(INSERT_BATCH + 5)]
    ids = server.repo().add_chunks(DOC_A, chunks)
    sent = [row for r in server.requests for row in json.loads(r.content)]
    assert ids == [row["id"] for row in sent] and len(set(ids)) == len(chunks)   # same order, all distinct
    assert all("user_id" not in row for row in sent)


def test_vectors_are_sent_as_text_in_batches_without_an_owner():
    server = Server(lambda r: httpx.Response(201))
    ids = [f"{i:036d}" for i in range(EMBED_BATCH * 2 + 7)]
    server.repo().add_embeddings(DOC_A, ids, [VEC] * len(ids), MODEL)
    batches = [json.loads(r.content) for r in server.requests]
    assert [len(b) for b in batches] == [EMBED_BATCH, EMBED_BATCH, 7]
    first = batches[0][0]
    assert first["chunk_id"] == ids[0] and first["model_id"] == MODEL
    assert first["embedding"].startswith("[0.25,") and first["embedding"].endswith("]")
    assert all("user_id" not in row for b in batches for row in b)
    assert all(r.headers["prefer"] == "return=minimal" and r.url.path.endswith("/embeddings") for r in server.requests)


def test_vectors_and_chunk_ids_must_line_up():
    server = Server(lambda r: httpx.Response(201))
    with pytest.raises(RepositoryError):
        server.repo().add_embeddings(DOC_A, ["a", "b"], [VEC], MODEL)
    assert server.requests == []


def test_mark_ready_records_the_embedding_model_only_when_there_is_one():
    server = Server(lambda r: httpx.Response(204))
    server.repo().mark_ready(DOC_A, MODEL)
    server.repo().mark_ready(DOC_A)
    assert json.loads(server.requests[0].content) == {"status": "ready", "embedding_model": MODEL}
    assert json.loads(server.requests[1].content) == {"status": "ready"}


def test_search_calls_the_database_function_as_the_user_with_only_indexed_documents():
    docs = [{"id": DOC_A, "name": "a.pdf", "embedding_model": MODEL}, {"id": DOC_B, "name": "b.pdf", "embedding_model": None}]
    server = Server(doc_rows(*docs))
    hits, not_indexed, total = server.repo("token-z").match_chunks(VEC, None, 4, MODEL)
    rpc = [r for r in server.requests if r.url.path.endswith("/rpc/match_chunks")][0]
    body = json.loads(rpc.content)
    assert rpc.headers["authorization"] == "Bearer token-z" and rpc.headers["apikey"] == KEY
    assert body["p_document_ids"] == [DOC_A] and body["p_match_count"] == 4 and body["p_model_id"] == MODEL
    assert body["p_query_embedding"].startswith("[0.25,")
    assert (not_indexed, total) == (1, 2)                                # b.pdf has no vectors
    assert [(h.page_number, round(score, 2)) for h, score in hits] == [(2, 0.91), (1, 0.62)]
    assert hits[0][0].filename == "a.pdf" and hits[0][0].chunk_id == f"{DOC_A}-p2-c0"


def test_documents_indexed_with_a_different_model_are_not_searched_with_this_one():
    server = Server(doc_rows({"id": DOC_A, "name": "a.pdf", "embedding_model": "some-other-model"}))
    assert server.repo().match_chunks(VEC, None, 4, MODEL) == ([], 1, 1)
    assert not any(r.url.path.endswith("/rpc/match_chunks") for r in server.requests)   # nothing to search


def test_no_documents_at_all_is_reported_as_zero_considered():
    server = Server(doc_rows())
    assert server.repo().match_chunks(VEC, None, 4, MODEL) == ([], 0, 0)


def test_a_document_that_is_not_the_callers_makes_the_search_return_none():
    server = Server(doc_rows({"id": DOC_A, "name": "a.pdf", "embedding_model": MODEL}))   # DOC_B is invisible (RLS)
    assert server.repo().match_chunks(VEC, [DOC_A, DOC_B], 4, MODEL) is None


def test_malformed_document_ids_never_reach_the_database():
    server = Server(doc_rows())
    assert server.repo().match_chunks(VEC, [DOC_A, "1) or (1=1"], 4, MODEL) is None
    assert server.requests == []


@pytest.mark.parametrize("stored,current,expected", [(MODEL, MODEL, True), (None, MODEL, False), ("old-model", MODEL, False), (MODEL, None, False)])
def test_a_document_is_semantic_only_if_indexed_with_the_current_model(stored, current, expected):
    row = {"id": DOC_A, "name": "a", "size_bytes": 1, "page_count": 1, "status": "ready", "embedding_model": stored, "chunks": [{"count": 2}]}
    server = Server(doc_rows(row))
    assert server.repo(model=current).list_documents()[0].semantic is expected
