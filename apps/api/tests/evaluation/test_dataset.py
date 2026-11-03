import pytest

from evaluation.dataset import Question, assign_splits, normalized_pages, relevant_pages, split, validate

PAGES = {
    "alpha": ["The six Functions are GOVERN,\nIDENTIFY and PROTECT.", "Quick-Start Guides are brief documents.", "Nothing relevant here."],
    "beta": ["The Senate shall be composed of two Senators.", "A page about sleep: adults need 7-8 hours."],
}
NORM = normalized_pages(PAGES)


def q(id="q1", type="direct", **kw):
    base = dict(id=id, type=type, author="assistant", question="A perfectly reasonable question?", doc="alpha",
                answer_spans=("quick-start guides are brief",))
    base.update(kw)
    return Question(**base)


# ------------------------------------------------------------------ relevance

def test_relevance_is_every_page_containing_any_answer_phrase():
    question = q(answer_spans=("Quick-Start Guides are brief", "composed of two Senators"))
    assert relevant_pages(question, NORM) == {("alpha", 2), ("beta", 1)}


def test_matching_ignores_case_and_line_breaks():
    assert relevant_pages(q(answer_spans=("governidentify",)), NORM) == set()
    assert relevant_pages(q(answer_spans=("GOVERN, IDENTIFY and protect",)), NORM) == {("alpha", 1)}


# ----------------------------------------------------------------- validation

def messages(*questions):
    return [i.message for i in validate(list(questions), PAGES)]


def test_a_well_formed_dataset_has_no_issues():
    good_unanswerable = q("u1", "unanswerable_related", answer_spans=(), absent_terms=("marbury",))
    assert validate([q(), good_unanswerable], PAGES) == []


def test_the_three_known_authors_are_accepted():
    for author in ("assistant", "owner", "external_llm"):
        assert validate([q(id=f"{author}-1", author=author)], PAGES) == []


def test_a_split_label_must_be_dev_or_test():
    assert validate([q(split="dev"), q("q2", split="test"), q("q3", split="")], PAGES) == []
    assert any("split must be" in m for m in messages(q(split="validation")))


def test_detects_duplicate_ids_unknown_types_and_authors():
    assert "duplicate id" in messages(q("same"), q("same"))
    assert any("unknown type" in m for m in messages(q(type="weird")))
    assert any("unknown author" in m for m in messages(q(author="somebody")))
    assert any("too short" in m for m in messages(q(question="Hi?")))


def test_every_answerable_question_needs_a_phrase_that_really_exists():
    assert any("needs answer_spans" in m for m in messages(q(answer_spans=())))
    assert any("not found in the corpus" in m for m in messages(q(answer_spans=("a phrase nobody wrote",))))


def test_a_phrase_must_live_in_the_stated_document():
    assert any("not in the stated document" in m for m in messages(q(doc="beta")))


def test_overly_generic_phrases_are_rejected():
    pages = {"d": [f"the same words appear everywhere {i}" for i in range(12)]}
    issues = validate([q(answer_spans=("the same words",), doc="d")], pages)
    assert any("too generic" in i.message for i in issues)


def test_unanswerable_questions_need_proof_the_answer_is_absent():
    assert any("needs absent_terms" in m for m in messages(q("u", "unanswerable_related", answer_spans=())))
    assert any("must not have answer_spans" in m for m in messages(q("u", "unanswerable_offtopic")))
    assert any("appears in the corpus" in m for m in messages(q("u", "unanswerable_related", answer_spans=(), absent_terms=("sleep",), doc="")))


def test_absence_is_checked_in_the_topical_document_only():
    # "sleep" appears in beta but not in alpha: a question about alpha is not made answerable by beta.
    assert validate([q("u", "unanswerable_related", answer_spans=(), absent_terms=("sleep",), doc="alpha")], PAGES) == []
    assert any("appears in the corpus" in m for m in messages(q("u", "unanswerable_related", answer_spans=(), absent_terms=("sleep",), doc="beta")))
    assert any("unknown document" in m for m in messages(q("u", "unanswerable_related", answer_spans=(), absent_terms=("x",), doc="gamma")))


def test_regex_absence_terms_use_word_boundaries():
    fine = q("u", "unanswerable_related", answer_spans=(), absent_terms=(r"re:\bsen(?:ate)?\b",), doc="beta")
    assert any("appears in the corpus" in m for m in messages(fine))
    assert validate([q("u", "unanswerable_related", answer_spans=(), absent_terms=(r"re:\bsenat$",), doc="beta")], PAGES) == []


# ---------------------------------------------------------------------- split

def population():
    out = []
    for t in ("direct", "paraphrase", "specific"):
        out += [q(f"{t}-{i}", t, author="assistant") for i in range(6)]
    out += [q(f"blind-{i}", "paraphrase", author="owner") for i in range(4)]
    out += [q(f"ext-{i}", "paraphrase", author="external_llm") for i in range(4)]
    out += [q(f"u-{i}", "unanswerable_offtopic", answer_spans=(), absent_terms=("zzz",)) for i in range(5)]
    return out


def test_assignment_is_stratified_by_type_and_author_deterministic_and_order_independent():
    qs = population()
    first = assign_splits(qs)
    assert first == assign_splits(qs) == assign_splits(list(reversed(qs)))
    assert set(first) == {x.id for x in qs} and set(first.values()) == {"dev", "test"}
    for key in {(x.type, x.author) for x in qs}:
        members = [x.id for x in qs if (x.type, x.author) == key]
        in_dev = sum(first[i] == "dev" for i in members)
        in_test = len(members) - in_dev
        assert in_dev >= in_test and in_dev - in_test <= 1 and in_test >= 1, key   # every author and type is in BOTH halves
    assert assign_splits(qs, seed=1) != assign_splits(qs, seed=2)


def test_a_frozen_label_always_wins():
    labeled = [q("a", split="test"), q("b", split="dev"), q("c", split="dev")]
    dev, test = split(labeled)
    assert [x.id for x in dev] == ["b", "c"] and [x.id for x in test] == ["a"]


def test_adding_questions_never_moves_an_existing_one():
    """The leak this prevents: a shuffle depends on who else is in the group, so adding questions
    could move a question whose results had already been examined into the held-out half."""
    original = population()
    before = {x.id: h for h, part in zip(("dev", "test"), split(original)) for x in part}
    extra = [q(f"new-{i}", "paraphrase") for i in range(7)]
    after = {x.id: h for h, part in zip(("dev", "test"), split(original + extra)) for x in part}
    assert all(after[i] == before[i] for i in before)


def test_unlabeled_questions_split_deterministically_and_disjointly():
    qs = population()
    dev, test = split(qs)
    assert (dev, test) == split(qs) == split(list(reversed(qs)))
    assert not {x.id for x in dev} & {x.id for x in test}
    assert {x.id for x in dev} | {x.id for x in test} == {x.id for x in qs}


def test_tiny_inputs_do_not_crash():
    assert assign_splits([q("only")]) == {"only": "dev"}
    dev, test = split([q("only", split="dev")])
    assert [x.id for x in dev] == ["only"] and test == []
