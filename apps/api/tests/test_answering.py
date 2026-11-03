import pytest

from app.answering import (
    ABSTAIN, SYSTEM_PROMPT, build_user_prompt, check_citations, is_abstention, select_for_context,
)
from app.retrieval import Hit, SearchChunk


def hit(n: int, text: str = "some evidence text", page: int = 1) -> Hit:
    return Hit(SearchChunk(f"c{n}", "d", "paper.pdf", page, text), 0.5)


def test_valid_citations_are_kept():
    out = check_citations("Alpha is true [1]. Beta too [2].", 2)
    assert out.text == "Alpha is true [1]. Beta too [2]." and out.cited == [1, 2] and out.removed == []


def test_invented_citation_is_stripped():
    out = check_citations("Alpha [1] and beta [9].", 2)
    assert out.text == "Alpha [1] and beta." and out.cited == [1] and out.removed == [9]


def test_grouped_citations_keep_only_valid_numbers():
    out = check_citations("Both agree [1, 7].", 3)
    assert out.text == "Both agree [1]." and out.removed == [7]
    assert check_citations("Nothing real [8, 9].", 3).cited == []


def test_zero_and_negative_style_numbers_are_invalid():
    out = check_citations("Bad [0].", 3)
    assert out.cited == [] and out.removed == [0]


def test_answer_without_citations_has_none():
    assert check_citations("A confident claim with no source.", 3).cited == []


def test_abstention_detection_is_forgiving_about_punctuation_only():
    assert is_abstention(ABSTAIN)
    assert is_abstention("  'I couldn't find that information in the uploaded documents'  ")
    assert not is_abstention("I couldn't find that, but it is probably 42 [1].")


def test_context_budget_drops_whole_chunks_but_keeps_the_best():
    hits = [hit(1, "a" * 500), hit(2, "b" * 500), hit(3, "c" * 500)]
    assert [h.chunk.chunk_id for h in select_for_context(hits, 1100)] == ["c1", "c2"]
    assert [h.chunk.chunk_id for h in select_for_context(hits, 10)] == ["c1"]  # best always kept
    assert select_for_context([], 100) == []


def test_prompt_numbers_evidence_and_labels_it_untrusted():
    prompt = build_user_prompt("What is X?", [hit(1, "X is 5", page=3), hit(2, "Y is 6", page=4)])
    assert "[1] paper.pdf, page 3\nX is 5" in prompt and "[2] paper.pdf, page 4\nY is 6" in prompt
    assert "untrusted" in prompt and prompt.rstrip().endswith("What is X?")


def test_system_prompt_states_the_grounding_rules():
    for phrase in ("ONLY", "untrusted", ABSTAIN, "Do not invent"):
        assert phrase in SYSTEM_PROMPT


@pytest.mark.parametrize("text", ["[1]", "see [1][2]", "x [ 1 ] y"])
def test_malformed_markers_do_not_crash(text):
    check_citations(text, 2)
