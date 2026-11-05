import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.ingestion import IngestionError, sanitize_filename
from app.main import app
from conftest import AUTH_A, USER_A, make_pdf

client = TestClient(app, headers=AUTH_A)


def upload(name: str, data: bytes, mime: str = "application/octet-stream"):
    return client.post("/api/v1/documents", files={"file": (name, data, mime)})


def test_two_page_pdf_keeps_true_page_numbers(fake_backend):
    pdf = make_pdf(["Introduction to extraction", "Random Forest selects difficulty"])
    res = upload("paper.pdf", pdf)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "ready" and body["page_count"] == 2 and body["chunk_count"] == 2
    chunks = fake_backend.chunks_of(USER_A.id, body["id"])
    assert [(c.page_number, c.chunk_index) for c in chunks] == [(1, 0), (2, 0)]
    assert "Random Forest" in chunks[1].text and "Random Forest" not in chunks[0].text


def test_blank_middle_page_does_not_shift_numbering(fake_backend):
    res = upload("gap.pdf", make_pdf(["first", "", "third"]))
    assert res.status_code == 201
    pages = [c.page_number for c in fake_backend.chunks_of(USER_A.id, res.json()["id"])]
    assert pages == [1, 3]


def test_text_and_markdown_upload_including_unicode():
    res = upload("notes.md", "# Título\n\nCafé — 数据".encode("utf-8"))
    assert res.status_code == 201 and res.json()["page_count"] == 1
    assert upload("plain.txt", b"hello world").status_code == 201


def test_long_text_produces_multiple_chunks():
    res = upload("long.txt", ("lorem ipsum dolor sit amet " * 200).encode())
    assert res.json()["chunk_count"] > 1


def test_list_and_get():
    doc_id = upload("a.txt", b"hello there").json()["id"]
    assert [d["id"] for d in client.get("/api/v1/documents").json()["documents"]] == [doc_id]
    assert client.get(f"/api/v1/documents/{doc_id}").json()["name"] == "a.txt"
    assert client.get("/api/v1/documents/missing").status_code == 404


def test_response_never_leaks_chunk_text():
    body = upload("secret.txt", b"classified content here").json()
    assert "chunks" not in body and "classified" not in str(body)


def test_rejects_unsupported_extension():
    assert upload("evil.exe", b"MZ").status_code == 400
    assert upload("noext", b"hello").status_code == 400


def test_rejects_fake_pdf_corrupt_pdf_and_bad_encoding():
    assert upload("fake.pdf", b"just text").status_code == 400
    assert upload("corrupt.pdf", b"%PDF-1.7 garbage garbage").status_code == 400
    assert upload("latin.txt", "café".encode("latin-1")).status_code == 400


def test_rejects_empty_and_whitespace_only():
    assert upload("empty.txt", b"").status_code == 422
    assert upload("blank.txt", b"  \n \n ").status_code == 422


def test_rejects_scanned_style_pdf_without_text():
    res = upload("scan.pdf", make_pdf(["", ""]))
    assert res.status_code == 422 and "OCR" in res.json()["detail"]


def test_rejects_encrypted_pdf():
    pdf = make_pdf(
        ["secret"], encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o"
    )
    res = upload("locked.pdf", pdf)
    assert res.status_code == 400 and "Encrypted" in res.json()["detail"]


def test_size_limit_boundary(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100")
    assert upload("ok.txt", b"a" * 100).status_code == 201
    assert upload("big.txt", b"a" * 101).status_code == 413


def test_pdf_page_limit(monkeypatch):
    monkeypatch.setenv("MAX_PDF_PAGES", "1")
    assert upload("two.pdf", make_pdf(["a", "b"])).status_code == 413
    assert upload("one.pdf", make_pdf(["a"])).status_code == 201


def test_document_count_limit(monkeypatch):
    monkeypatch.setenv("MAX_DOCUMENTS", "2")
    assert upload("1.txt", b"one").status_code == 201
    assert upload("2.txt", b"two").status_code == 201
    assert upload("3.txt", b"three").status_code == 409
    assert len(client.get("/api/v1/documents").json()["documents"]) == 2


def test_failed_upload_leaves_no_partial_record():
    upload("bad.pdf", b"nope")
    assert client.get("/api/v1/documents").json()["documents"] == []


def test_path_traversal_in_filename_is_stripped():
    res = upload("../../etc/passwd.txt", b"hello")
    assert res.status_code == 201 and res.json()["name"] == "passwd.txt"


def test_sanitize_filename_directly():
    # Called directly: HTTP clients percent-encode control chars before they arrive.
    assert sanitize_filename("a\x00b\x1f.txt") == "ab.txt"
    assert sanitize_filename("C:\\Users\\me\\notes.md") == "notes.md"
    assert len(sanitize_filename("x" * 500 + ".txt")) <= 130
    with pytest.raises(IngestionError):
        sanitize_filename(None)


# ---- abandoned uploads are cleaned up when the owner lists their documents --------------------

def test_listing_removes_the_callers_abandoned_uploads_only(fake_backend, monkeypatch):
    from conftest import AUTH_A, USER_A, USER_B
    from fastapi.testclient import TestClient
    from app.main import app

    now = [1000.0]
    fake_backend.clock = lambda: now[0]
    a_repo, b_repo = fake_backend.repo_for(USER_A), fake_backend.repo_for(USER_B)
    stuck_a, stuck_b = a_repo.create_document("a.pdf", 1, 1), b_repo.create_document("b.pdf", 1, 1)
    now[0] += 16 * 60                                          # 16 minutes later (the cutoff is 15)
    fresh_a = a_repo.create_document("fresh.pdf", 1, 1)         # just started

    listing = TestClient(app, headers=AUTH_A).get("/api/v1/documents").json()["documents"]
    assert {d["id"] for d in listing} == {fresh_a.id}           # stuck one gone, fresh one kept
    assert b_repo.get_document(stuck_b.id) is not None          # another user's stuck upload is theirs to clean
    assert stuck_a.id not in {d["id"] for d in listing}


def test_a_failing_cleanup_never_breaks_listing(fake_backend, monkeypatch):
    from conftest import AUTH_A, USER_A
    from fastapi.testclient import TestClient
    from app.main import app

    repo = fake_backend.repo_for(USER_A)
    doc = repo.create_document("keep.pdf", 1, 1)
    repo.mark_ready(doc.id)

    def broken(self, older_than_seconds):
        raise RuntimeError("storage exploded with secret detail")

    monkeypatch.setattr(type(repo), "remove_abandoned_uploads", broken)
    res = TestClient(app, headers=AUTH_A).get("/api/v1/documents")
    assert res.status_code == 200 and [d["id"] for d in res.json()["documents"]] == [doc.id]
    assert "secret detail" not in res.text
