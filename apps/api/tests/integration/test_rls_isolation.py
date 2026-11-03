"""Two-account isolation tests for the M6a schema (see docs/m6-plan.md).

Every denial test is paired with a positive control (the owner CAN do the thing),
so a test cannot pass just because everything is broken or misconfigured.
"""
import pytest
from supabase_helpers import (  # noqa: F401  (fixtures are used by name)
    DOC, chunk_payload, doc_a, rest, skip_without_supabase, user_a, user_b,
)

pytestmark = [pytest.mark.integration, skip_without_supabase]

DENIED = (401, 403)  # PostgREST: 42501 "insufficient privilege" / RLS violation


def denied(response) -> bool:
    return response.status_code in DENIED and "42501" in response.text


# ----------------------------------------------------------- anonymous access

@pytest.mark.parametrize("table", ["profiles", "documents", "chunks"])
def test_anonymous_cannot_read_or_write_anything(table):
    assert rest("GET", table).status_code in DENIED
    assert rest("POST", table, json={}).status_code in DENIED


# ------------------------------------------------------------ owner positives

def test_owner_can_create_read_rename_and_delete(user_a):
    created = rest("POST", "documents", user_a, json=DOC)
    assert created.status_code == 201
    doc = created.json()[0]
    assert doc["user_id"] == user_a.id            # defaulted from the token, not chosen by the client
    assert doc["status"] == "ready"
    assert rest("GET", f"documents?id=eq.{doc['id']}", user_a).json()[0]["name"] == "notes.pdf"
    renamed = rest("PATCH", f"documents?id=eq.{doc['id']}", user_a, json={"name": "renamed.pdf"})
    assert renamed.status_code == 200 and renamed.json()[0]["name"] == "renamed.pdf"
    assert rest("DELETE", f"documents?id=eq.{doc['id']}", user_a).json()[0]["id"] == doc["id"]
    assert rest("GET", f"documents?id=eq.{doc['id']}", user_a).json() == []


# --------------------------------------------------- cross-user (IDOR) attempts

def test_other_user_cannot_see_update_or_delete_my_document(user_a, user_b, doc_a):
    path = f"documents?id=eq.{doc_a['id']}"
    assert rest("GET", path, user_a).json()[0]["id"] == doc_a["id"]      # positive control
    assert rest("GET", "documents", user_b).json() == []                  # not in B's list
    assert rest("GET", path, user_b).json() == []                         # not by id either
    assert rest("PATCH", path, user_b, json={"name": "hacked"}).json() == []   # touches zero rows
    assert rest("DELETE", path, user_b).json() == []
    still = rest("GET", path, user_a).json()
    assert still and still[0]["name"] == DOC["name"]                      # untouched


def test_cannot_insert_a_document_owned_by_someone_else(user_a, user_b):
    forged = rest("POST", "documents", user_b, json={**DOC, "user_id": user_a.id})
    assert denied(forged), forged.text
    assert rest("GET", "documents", user_a).json() == []                  # nothing appeared for A


def test_cannot_reassign_ownership_or_edit_protected_columns(user_a, user_b, doc_a):
    path = f"documents?id=eq.{doc_a['id']}"
    assert denied(rest("PATCH", path, user_a, json={"user_id": user_b.id}))   # column privilege
    assert denied(rest("PATCH", path, user_a, json={"size_bytes": 1}))
    assert denied(rest("PATCH", path, user_a, json={"created_at": "2000-01-01T00:00:00Z"}))
    row = rest("GET", path, user_a).json()[0]
    assert row["user_id"] == user_a.id and row["size_bytes"] == DOC["size_bytes"]
    assert rest("PATCH", path, user_a, json={"status": "deleting"}).status_code == 200   # allowed column


# ------------------------------------------------------------------- chunks

def test_chunks_belong_to_their_owner_and_are_immutable(user_a, user_b, doc_a):
    made = rest("POST", "chunks", user_a, json=chunk_payload(doc_a["id"]))
    assert made.status_code == 201, made.text
    chunk = made.json()[0]
    assert chunk["user_id"] == user_a.id
    path = f"chunks?id=eq.{chunk['id']}"
    assert rest("GET", path, user_a).json()[0]["text"] == "hello"         # positive control
    assert rest("GET", path, user_b).json() == []
    assert rest("DELETE", path, user_b).json() == []
    assert denied(rest("PATCH", path, user_a, json={"text": "edited"}))   # nobody may edit a chunk
    assert rest("GET", path, user_a).json()[0]["text"] == "hello"


def test_cannot_attach_a_chunk_to_someone_elses_document(user_a, user_b, doc_a):
    # Passes RLS (user_id is B's own) but must fail the composite foreign key,
    # because the pair (A's document, B) does not exist. If that key is removed,
    # this is the test that fails.
    attached = rest("POST", "chunks", user_b, json=chunk_payload(doc_a["id"], user_id=user_b.id))
    assert attached.status_code == 409 and "23503" in attached.text, attached.text
    # Claiming A's identity instead is stopped by RLS.
    impersonated = rest("POST", "chunks", user_b, json=chunk_payload(doc_a["id"], user_id=user_a.id))
    assert denied(impersonated), impersonated.text
    assert rest("GET", f"chunks?document_id=eq.{doc_a['id']}", user_a).json() == []


def test_deleting_a_document_deletes_its_chunks(user_a):
    doc = rest("POST", "documents", user_a, json=DOC).json()[0]
    assert rest("POST", "chunks", user_a, json=chunk_payload(doc["id"])).status_code == 201
    assert len(rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()) == 1
    rest("DELETE", f"documents?id=eq.{doc['id']}", user_a)
    assert rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json() == []


# ----------------------------------------------------------------- profiles

def test_profiles_are_created_on_signup_and_private(user_a, user_b):
    mine = rest("GET", "profiles", user_a).json()
    assert [p["id"] for p in mine] == [user_a.id]                          # created by the trigger
    assert rest("GET", f"profiles?id=eq.{user_a.id}", user_b).json() == []
    assert rest("PATCH", f"profiles?id=eq.{user_a.id}", user_a, json={"display_name": "Ada"}).status_code == 200
    assert denied(rest("PATCH", f"profiles?id=eq.{user_a.id}", user_a, json={"id": user_b.id}))
    assert rest("PATCH", f"profiles?id=eq.{user_a.id}", user_b, json={"display_name": "x"}).json() == []


# ------------------------------------------------------------------- tokens

def test_a_tampered_token_is_rejected(user_a):
    assert rest("GET", "documents", user_a).status_code == 200            # positive control
    flipped = user_a.token[:-4] + ("AAAA" if not user_a.token.endswith("AAAA") else "BBBB")
    assert rest("GET", "documents", token=flipped).status_code == 401
    assert rest("GET", "documents", token="not-a-jwt").status_code == 401
