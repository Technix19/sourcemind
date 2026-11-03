"""Integrity of the REAL evaluation data. Skipped unless the PDFs have been fetched
(python data/evaluation/fetch_corpus.py)."""
import hashlib

import pytest

from evaluation.corpus import CORPUS_DIR, QUESTION_FILES, corpus_available, load_manifest, load_pages
from evaluation.dataset import load_questions, normalized_pages, relevant_pages, split, validate

pytestmark = pytest.mark.skipif(not corpus_available(), reason="run data/evaluation/fetch_corpus.py first")


@pytest.fixture(scope="module")
def pages():
    return load_pages()


@pytest.fixture(scope="module")
def questions():
    return load_questions(*QUESTION_FILES)


def test_every_corpus_file_matches_its_recorded_hash():
    for doc in load_manifest()["documents"]:
        assert hashlib.sha256((CORPUS_DIR / doc["file"]).read_bytes()).hexdigest() == doc["sha256"], doc["id"]


def test_every_label_is_valid(questions, pages):
    issues = validate(questions, pages)
    assert issues == [], [f"{i.question_id}: {i.message}" for i in issues]


def test_the_dataset_has_the_size_and_balance_the_design_requires(questions):
    kinds = {t: sum(q.type == t for q in questions) for t in {q.type for q in questions}}
    assert len(questions) >= 30
    assert all(kinds.get(t, 0) >= 5 for t in ("direct", "paraphrase", "specific", "unanswerable_related", "unanswerable_offtopic")), kinds


def test_every_document_is_covered_by_at_least_three_answerable_questions(questions):
    for doc in load_manifest()["documents"]:
        assert sum(q.doc == doc["id"] and q.answerable for q in questions) >= 3, doc["id"]


def test_every_answerable_question_has_a_small_nonempty_set_of_relevant_pages(questions, pages):
    norm = normalized_pages(pages)
    for q in questions:
        if q.answerable:
            assert 1 <= len(relevant_pages(q, norm)) <= 8, q.id


# The development half of batch 1, frozen BEFORE the held-out half was ever scored. These are the questions whose
# per-question retrieval results had been examined, so they must never be moved into the test half.
BATCH1_DEV = {"con-02", "con-05", "con-06", "csf-04", "csf-05", "csf-06", "fed-01", "fed-02", "fed-03", "fed-06", "off-01",
              "off-02", "off-04", "rmf-01", "rmf-02", "rmf-04", "sleep-01", "sleep-04", "sleep-05"}


def test_every_question_has_a_frozen_split_label(questions):
    assert [q.id for q in questions if q.split not in ("dev", "test")] == []


def test_the_frozen_assignment_of_batch_one_has_not_changed(questions):
    batch1 = [q for q in questions if q.author == "assistant" and not q.id.startswith("x-")]
    assert {q.id for q in batch1 if q.split == "dev"} == BATCH1_DEV
    assert all(q.split == "test" for q in batch1 if q.id not in BATCH1_DEV)


def test_both_halves_of_the_split_contain_every_question_kind(questions):
    dev, test = split(questions)
    for part in (dev, test):
        assert {q.type for q in part} == {q.type for q in questions}
