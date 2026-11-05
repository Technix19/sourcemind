"""The generation evaluation. A fake model throughout: no network, no cost, no key."""
import types

import pytest
from fastapi.testclient import TestClient

from app.answering import ABSTAIN, SYSTEM_PROMPT
from app.llm import GenerationRefused
from app.main import app
from app.retrieval import Hit, SearchChunk
from conftest import AUTH_A
from evaluation import generation as gen
from evaluation.dataset import Question

REL = {("doc", 2)}


def q(qid="q1", kind="direct"):
    return Question(id=qid, type=kind, author="assistant", question="Which classifier selects difficulty?")


def hit(page, text="chunk text", doc="doc"):
    return Hit(SearchChunk(f"{doc}-p{page}-c0", doc, f"{doc}.pdf", page, text), 0.5)


class FakeClient:
    model = "fake-model"

    def __init__(self, reply="", error=None):
        self.reply, self.error, self.calls, self.last_usage = reply, error, [], None

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.error:
            raise self.error
        self.last_usage = {"input_tokens": 100, "output_tokens": 20}
        return self.reply


def run(client, hits, question=None, relevant=REL):
    return gen.run_question(question or q(), hits, client, 8000, relevant)


# ---- outcomes -----------------------------------------------------------------------------

def test_no_hits_means_no_model_call_and_a_no_evidence_outcome():
    client = FakeClient("should not be used [1]")
    record = run(client, [])
    assert record["outcome"] == "no_evidence" and client.calls == [] and record["evidence_has_answer"] is False


def test_the_exact_abstention_sentence_is_an_abstention():
    record = run(FakeClient(ABSTAIN), [hit(2)])
    assert record["outcome"] == "abstained"


def test_an_answer_with_no_valid_citation_is_withheld():
    assert run(FakeClient("A confident answer with no citation."), [hit(2)])["outcome"] == "withheld"
    only_invalid = run(FakeClient("It is X [9]."), [hit(2)])
    assert only_invalid["outcome"] == "withheld" and only_invalid["invalid_citations"] == [9]


def test_a_citation_on_a_relevant_page_is_supported():
    record = run(FakeClient("Random Forest [1]."), [hit(2)])
    assert record["outcome"] == "answered" and record["supported"] is True and record["cited"] == [1]


def test_a_citation_on_an_irrelevant_page_is_answered_but_not_supported():
    record = run(FakeClient("It is X [1]."), [hit(7), hit(2)])
    assert record["outcome"] == "answered" and record["supported"] is False and record["evidence_has_answer"] is True


def test_support_follows_the_cited_passage_not_just_any_passage_sent():
    both = [hit(7), hit(2)]
    assert run(FakeClient("From the second [2]."), both)["supported"] is True
    assert run(FakeClient("From the first [1]."), both)["supported"] is False


def test_failures_are_errors_never_successes_and_carry_no_message():
    boom = run(FakeClient(error=RuntimeError("secret key sk-123 leaked")), [hit(2)])
    assert boom["outcome"] == "error" and boom["reason"] == "RuntimeError" and "sk-123" not in str(boom)
    assert run(FakeClient(error=GenerationRefused()), [hit(2)])["reason"] == "refusal"


def test_token_usage_and_latency_are_recorded_for_cost_tracking():
    record = run(FakeClient("Yes [1]."), [hit(2)])
    assert record["usage"] == {"input_tokens": 100, "output_tokens": 20} and record["latency_ms"] >= 0


def test_the_context_budget_limits_what_is_sent_and_what_counts_as_evidence():
    big = [hit(7, "a" * 6000), hit(2, "b" * 6000)]
    client = FakeClient("Yes [1].")
    record = gen.run_question(q(), big, client, 8000, REL)
    assert record["evidence"] == [["doc", 7]] and record["evidence_has_answer"] is False   # the relevant page did not fit
    user_prompt = client.calls[0][1]
    assert "a" * 6000 in user_prompt and "b" * 6000 not in user_prompt                    # and the model never saw it


# ---- parity with the product --------------------------------------------------------------

def test_the_harness_sends_the_model_exactly_what_the_api_sends():
    """Run the real endpoint with a capturing model, then give the harness the same evidence."""
    product_llm = FakeClient("The classifier does it [1].")
    import app.main as main
    original = main.get_llm_client
    main.get_llm_client = lambda: product_llm
    try:
        client = TestClient(app, headers=AUTH_A)
        up = client.post("/api/v1/documents", files={"file": ("paper.txt", b"The Random Forest classifier selects question difficulty from correctness.", "text/plain")})
        assert up.status_code == 201
        body = client.post("/api/v1/queries", json={"question": "Which classifier selects difficulty?", "mode": "generated"}).json()
    finally:
        main.get_llm_client = original
    assert body["answer_mode"] == "generated" and len(product_llm.calls) == 1
    hits = [Hit(SearchChunk(e["chunk_id"], e["document_id"], e["filename"], e["page_number"], e["excerpt"]), e["score"]) for e in body["evidence"]]
    harness_llm = FakeClient("The classifier does it [1].")
    gen.run_question(q(), hits, harness_llm, 8000, set())
    assert harness_llm.calls == product_llm.calls                    # identical (system prompt, user prompt)
    assert harness_llm.calls[0][0] == SYSTEM_PROMPT


# ---- aggregation --------------------------------------------------------------------------

def rec(qid, answerable, outcome, has_answer=True, supported=None):
    r = {"id": qid, "answerable": answerable, "outcome": outcome, "evidence_has_answer": has_answer}
    if supported is not None:
        r["supported"] = supported
    return r


def test_metrics_use_the_denominators_the_plan_fixed():
    records = [
        rec("a1", True, "answered", True, True), rec("a2", True, "answered", True, False),
        rec("a3", True, "abstained", True), rec("a4", True, "withheld", True),
        rec("b1", True, "answered", False, False), rec("b2", True, "no_evidence", False),
        rec("u1", False, "no_evidence", False), rec("u2", False, "abstained", True), rec("u3", False, "answered", True, False),
    ]
    m = gen.aggregate(records)
    assert m["answerable_with_evidence"]["answer_rate"]["value"] == 0.5 and m["answerable_with_evidence"]["answer_rate"]["n"] == 4
    assert m["answerable_with_evidence"]["supported_citation_rate"]["value"] == 0.5     # of the 2 answered
    assert m["answerable_with_evidence"]["supported_citation_rate"]["n"] == 2
    assert m["answerable_with_evidence"]["wrong_abstention_rate"]["value"] == 0.25
    assert m["answerable_without_evidence"]["answered_anyway"]["value"] == 0.5 and m["answerable_without_evidence"]["answered_anyway"]["n"] == 2
    assert m["unanswerable"]["invented_answer_rate"]["value"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["unanswerable"]["product_abstained"]["value"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["unanswerable"]["model_was_called"] == 2                                   # u2 and u3
    assert m["outcomes"] == {"no_evidence": 2, "abstained": 2, "withheld": 1, "answered": 4, "error": 0}


def test_empty_groups_give_no_number_instead_of_a_fake_zero():
    m = gen.aggregate([rec("u1", False, "no_evidence", False)])
    assert m["answerable_with_evidence"]["answer_rate"]["value"] is None


def test_the_preregistered_concerns_are_flagged():
    clean = gen.aggregate([rec("a1", True, "answered", True, True), rec("u1", False, "abstained", True)])
    assert clean["concerns"] == []
    bad = gen.aggregate([rec("a1", True, "answered", True, False), rec("u1", False, "answered", True, False),
                         {**rec("a2", True, "error", True), "reason": "refusal"}])
    text = " | ".join(bad["concerns"])
    assert "unanswerable question: u1" in text and "below the 0.80 line" in text and "failed on a2" in text


def test_outcomes_that_change_between_runs_are_reported():
    run1 = [rec("a", True, "answered"), rec("b", True, "abstained")]
    run2 = [rec("a", True, "answered"), rec("b", True, "answered")]
    assert gen.unstable([run1, run2]) == [{"id": "b", "outcomes": ["abstained", "answered"]}]
    assert gen.unstable([run1, run1]) == []


# ---- retrieval settings and safety gates --------------------------------------------------

class FakeArm:
    def __init__(self, scores):
        self.scores = scores

    def search(self, question, n):
        ranked = [types.SimpleNamespace(score=s, chunk=types.SimpleNamespace(doc_id="doc", page=i + 1, index=0, text=f"t{i}"))
                  for i, s in enumerate(self.scores)]
        return types.SimpleNamespace(ranked=ranked)


def test_retrieval_keeps_the_top_k_at_or_above_the_product_threshold():
    hits = gen.hits_for(FakeArm([0.9, 0.5, 0.05, 0.049, 0.01]), "q", {"doc": "doc.pdf"}, 0.05, top_k=4)
    assert [h.chunk.page_number for h in hits] == [1, 2, 3] and hits[0].chunk.filename == "doc.pdf"
    assert gen.hits_for(FakeArm([0.9] * 9), "q", {}, 0.05)[3].chunk.page_number == 4 and len(gen.hits_for(FakeArm([0.9] * 9), "q", {}, 0.05)) == 4


def test_it_refuses_to_spend_money_without_explicit_confirmation(monkeypatch, capsys):
    monkeypatch.setattr(gen, "get_llm_client", lambda: pytest.fail("must not even build a client"))
    assert gen.main(["--runs", "1"]) == 2
    assert "--confirm-spend" in capsys.readouterr().out


def test_it_refuses_to_run_when_generation_is_not_configured(monkeypatch, capsys):
    monkeypatch.setattr(gen, "get_llm_client", lambda: None)
    assert gen.main(["--confirm-spend"]) == 2
    assert "not configured" in capsys.readouterr().out


def test_the_report_states_its_limits_and_the_plan():
    results = {"run": {"date": "2026-11-05", "git": {"commit": "abc", "dirty": False}, "model": "m", "effort": "low", "max_tokens": 2000,
                       "top_k": 4, "min_relevance_score": 0.05, "max_context_chars": 8000, "questions": 2, "runs": 1},
               "runs": [{"records": [], "metrics": gen.aggregate([rec("a", True, "answered", True, True), rec("u", False, "abstained")])}],
               "unstable_questions": []}
    text = gen.build_report(results)
    assert "not that the answer text is true" in text and "docs/m8-generation-eval.md" in text
    assert "None of the pre-registered concern lines" in text and "No question changed outcome" in text
