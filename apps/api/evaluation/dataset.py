"""Labeled questions, mechanical relevance, validation, and a deterministic dev/test split.

Relevance is MECHANICAL: a page is relevant to an answerable question if any of the question's
`answer_spans` (literal phrases) appears on it. No hand-picked page numbers can drift, and
facts repeated across pages (e.g. in an index) are handled consistently.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from .corpus import normalize

TYPES = ("direct", "paraphrase", "specific", "unanswerable_related", "unanswerable_offtopic")
ANSWERABLE = ("direct", "paraphrase", "specific")
AUTHORS = ("assistant", "owner", "external_llm")
MAX_RELEVANT_PAGES = 8   # a phrase matching more pages than this is probably too generic to be a label


@dataclass(frozen=True)
class Question:
    id: str
    type: str
    author: str                     # "assistant", "owner" (written blind) or "external_llm" (another AI, also blind)
    question: str
    answer: str = ""
    doc: str = ""                   # the document the answer is in (a hint; relevance comes from the spans)
    answer_spans: tuple[str, ...] = ()
    absent_terms: tuple[str, ...] = ()   # for unanswerable questions: must NOT appear anywhere in the corpus
    split: str = ""                 # "dev" or "test", FROZEN in the data file; empty = not assigned yet

    @property
    def answerable(self) -> bool:
        return self.type in ANSWERABLE


def load_questions(*paths: Path) -> list[Question]:
    questions: list[Question] = []
    for path in paths:
        if not path.exists():
            continue
        for raw in json.loads(path.read_text())["questions"]:
            questions.append(Question(
                id=raw["id"], type=raw["type"], author=raw.get("author", "assistant"), question=raw["question"],
                answer=raw.get("answer", ""), doc=raw.get("doc", ""),
                answer_spans=tuple(raw.get("answer_spans", ())), absent_terms=tuple(raw.get("absent_terms", ())),
                split=raw.get("split", ""),
            ))
    return questions


def _term_regex(term: str) -> re.Pattern:
    """Plain substring (case-insensitive), or a regex when written as 're:...'."""
    return re.compile(term[3:] if term.startswith("re:") else re.escape(term), re.I)


def normalized_pages(pages: dict[str, list[str]]) -> dict[str, list[str]]:
    return {doc: [normalize(p) for p in doc_pages] for doc, doc_pages in pages.items()}


def relevant_pages(question: Question, norm: dict[str, list[str]]) -> set[tuple[str, int]]:
    """Every (doc, page) where any of the answer phrases appears."""
    found: set[tuple[str, int]] = set()
    spans = [normalize(s) for s in question.answer_spans]
    for doc, doc_pages in norm.items():
        for page_number, text in enumerate(doc_pages, start=1):
            if any(span and span in text for span in spans):
                found.add((doc, page_number))
    return found


@dataclass
class Issue:
    question_id: str
    message: str


def validate(questions: list[Question], pages: dict[str, list[str]]) -> list[Issue]:
    """Everything that must be true for the labels to be trustworthy. An empty list means valid."""
    issues: list[Issue] = []
    norm = normalized_pages(pages)
    seen: set[str] = set()
    for q in questions:
        if q.id in seen:
            issues.append(Issue(q.id, "duplicate id"))
        seen.add(q.id)
        if q.type not in TYPES:
            issues.append(Issue(q.id, f"unknown type {q.type!r}"))
            continue
        if q.split not in ("", "dev", "test"):
            issues.append(Issue(q.id, f"split must be 'dev' or 'test', got {q.split!r}"))
        if q.author not in AUTHORS:
            issues.append(Issue(q.id, f"unknown author {q.author!r}"))
        if len(q.question.strip()) < 8:
            issues.append(Issue(q.id, "question is too short"))
        if q.answerable:
            if not q.answer_spans:
                issues.append(Issue(q.id, "an answerable question needs answer_spans"))
                continue
            for span in q.answer_spans:
                if not any(normalize(span) in p for dp in norm.values() for p in dp):
                    issues.append(Issue(q.id, f"answer phrase not found in the corpus: {span!r}"))
            rel = relevant_pages(q, norm)
            if not rel:
                issues.append(Issue(q.id, "no relevant page found"))
            elif len(rel) > MAX_RELEVANT_PAGES:
                issues.append(Issue(q.id, f"answer phrase matches {len(rel)} pages (max {MAX_RELEVANT_PAGES}); it is too generic"))
            if q.doc and rel and not any(d == q.doc for d, _ in rel):
                issues.append(Issue(q.id, f"phrase is not in the stated document {q.doc!r}"))
        else:
            if q.answer_spans:
                issues.append(Issue(q.id, "an unanswerable question must not have answer_spans"))
            if q.type == "unanswerable_related" and not q.absent_terms:
                issues.append(Issue(q.id, "unanswerable_related needs absent_terms to prove the answer is not in the corpus"))
            if q.doc and q.doc not in pages:
                issues.append(Issue(q.id, f"unknown document {q.doc!r}"))
            # Scope: the topical document when given (a question about NIST penalties is not made
            # answerable by a history lesson in another document), the whole corpus otherwise.
            scope = {q.doc: pages[q.doc]} if q.doc in pages else pages
            for term in q.absent_terms:
                rx = _term_regex(term)
                hits = [(d, n) for d, dp in scope.items() for n, text in enumerate(dp, start=1) if rx.search(text)]
                if hits:
                    issues.append(Issue(q.id, f"absent term {term!r} appears in the corpus, e.g. {hits[0]}"))
    return issues


def assign_splits(questions: list[Question], seed: int = 20261103) -> dict[str, str]:
    """Stratified dev/test assignment for the GIVEN questions: about half of each (type, author) group in each part.

    This is used ONCE per batch of new questions; the result is then written into the data file
    (see evaluation.tools assign), because a shuffle depends on who else is in the group and would
    otherwise move existing questions around whenever new ones are added.
    """
    groups: dict[tuple[str, str], list[Question]] = {}
    for q in sorted(questions, key=lambda q: q.id):
        groups.setdefault((q.type, q.author), []).append(q)
    assignment: dict[str, str] = {}
    for key in sorted(groups):
        members = groups[key]
        random.Random(f"{seed}:{key}").shuffle(members)
        cut = math.ceil(len(members) / 2)
        for q in members[:cut]:
            assignment[q.id] = "dev"
        for q in members[cut:]:
            assignment[q.id] = "test"
    return assignment


def _fallback_half(question_id: str, seed: int) -> str:
    """Per-question and independent of every other question, so adding questions never moves an existing one."""
    digest = hashlib.sha256(f"{seed}:{question_id}".encode()).digest()
    return "dev" if digest[0] % 2 == 0 else "test"


def split(questions: list[Question], seed: int = 20261103) -> tuple[list[Question], list[Question]]:
    """Dev/test halves. A question's frozen `split` label always wins; an unlabeled one falls back to a
    stable per-question hash. Thresholds are tuned on dev only; every headline number is reported on test.
    """
    dev: list[Question] = []
    test: list[Question] = []
    for q in sorted(questions, key=lambda q: q.id):
        half = q.split or _fallback_half(q.id, seed)
        (dev if half == "dev" else test).append(q)
    return dev, test
