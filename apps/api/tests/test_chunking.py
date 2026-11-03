import pytest

from app.chunking import chunk_text, clean_text


def test_clean_text_keeps_paragraphs_and_collapses_spaces():
    assert clean_text("  a   b \n\n\n\n c\t d  ") == "a b\n\nc d"


def test_short_and_empty_text():
    assert chunk_text("") == []
    chunks = chunk_text("hello world")
    assert [c.text for c in chunks] == ["hello world"]
    assert (chunks[0].start, chunks[0].end) == (0, 11)


def test_offsets_point_back_into_source_text():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    for c in chunks:
        assert text[c.start:c.end] == c.text
        assert len(c.text) <= 200
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunks_overlap_and_cover_everything():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    for a, b in zip(chunks, chunks[1:]):
        assert b.start < a.end, "consecutive chunks should overlap"
        assert b.start > a.start, "must always make progress"
    assert chunks[0].start == 0 and chunks[-1].end == len(text)


def test_chunks_start_on_word_boundaries():
    text = " ".join(f"word{i}" for i in range(400))
    for c in chunk_text(text, chunk_size=200, overlap=40):
        assert c.text.startswith("word") and c.text.split()[-1].startswith("word")


def test_prefers_paragraph_boundary():
    text = ("a" * 30 + " ") * 5 + "\n\n" + ("b " * 60)
    first = chunk_text(text, chunk_size=200, overlap=20)[0]
    assert first.text.endswith("a") and "b" not in first.text


def test_unbroken_text_is_hard_cut_without_looping():
    chunks = chunk_text("x" * 1000, chunk_size=200, overlap=40)
    assert len(chunks) > 1 and chunks[-1].end == 1000


def test_deterministic_and_unicode_safe():
    text = "Résumé naïve café — 数据 " * 100
    assert chunk_text(text, chunk_size=150, overlap=30) == chunk_text(text, chunk_size=150, overlap=30)


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 50), (100, -1), (100, 100)])
def test_invalid_parameters_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=size, overlap=overlap)


def test_nul_characters_are_removed_because_postgres_text_cannot_store_them():
    assert clean_text("ab\x00cd \x00 ef") == "abcd ef"
    assert all("\x00" not in c.text for c in chunk_text(clean_text("x\x00y " * 400), chunk_size=100, overlap=10))
