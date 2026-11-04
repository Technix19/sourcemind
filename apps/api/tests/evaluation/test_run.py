import json

import pytest

import evaluation.arms as arms_module
import evaluation.run as run_module
from conftest import FakeEmbedder
from evaluation.dataset import Question
from evaluation.run import operating_point, passes, report_arm, returned_pages, sweep

PAGES = {
    "alpha": [
        "The classifier selects the next practice difficulty for each learner using correctness and attempts.",
        "Sleep needs change throughout the life cycle: newborns sleep many hours a day.",
        "The central bank sets interest rates to keep prices stable and employment high.",
    ],
    "beta": ["Voting age was lowered to eighteen by an amendment.", "Senators serve six year terms in the upper chamber."],
}
QUESTIONS = [
    Question("a1", "direct", "assistant", "Which classifier selects practice difficulty?", doc="alpha", answer_spans=("classifier selects the next practice difficulty",), split="dev"),
    Question("a2", "specific", "assistant", "How long do Senators serve?", doc="beta", answer_spans=("six year terms",), split="dev"),
    Question("a3", "paraphrase", "owner", "What do newborns do all day?", doc="alpha", answer_spans=("newborns sleep many hours",), split="dev"),
    Question("u1", "unanswerable_offtopic", "assistant", "What is the capital of Australia?", absent_terms=("canberra",), split="dev"),
    Question("u2", "unanswerable_related", "assistant", "Which bank fined the Fed?", doc="alpha", absent_terms=("fined",), split="dev"),
    # a second member of every stratum, so that both halves of the split are non-empty
    Question("b1", "direct", "assistant", "Which classifier chooses the practice difficulty?", doc="alpha", answer_spans=("classifier selects the next practice difficulty",), split="test"),
    Question("b2", "specific", "assistant", "How many years do Senators serve?", doc="beta", answer_spans=("six year terms",), split="test"),
    Question("b3", "paraphrase", "owner", "What do babies do most of the day?", doc="alpha", answer_spans=("newborns sleep many hours",), split="test"),
    Question("v1", "unanswerable_offtopic", "assistant", "Who won the 2018 football world cup?", absent_terms=("football",), split="test"),
    Question("v2", "unanswerable_related", "assistant", "Which bank was penalised by the Fed?", doc="alpha", absent_terms=("penalised",), split="test"),
]


def without_timing(report: dict) -> dict:
    """Latencies are measured, so they legitimately differ between runs; everything else must not."""
    clean = json.loads(json.dumps(report))
    clean.pop("product_tfidf_latency_ms", None)
    for arm in clean["arms"].values():
        arm.pop("latency_ms", None)
        for rec in arm["per_question"]:
            rec.pop("latency_ms", None)
    return clean


def record(id, answerable, gate, ranked, relevant=None, **extra):
    base = {"id": id, "type": "direct" if answerable else "unanswerable_offtopic", "author": "assistant", "answerable": answerable,
            "question": "q", "gate": gate, "latency_ms": 1.0, "ranked": ranked}
    if answerable:
        base |= {"relevant": relevant}
    return base | extra


# ---------------------------------------------------------------- operating point

def test_a_method_returns_something_if_any_component_clears_its_threshold():
    assert passes({"tfidf": 0.2, "embedding": 0.4}, {"tfidf": 0.1, "embedding": 0.9}) is True
    assert passes({"tfidf": 0.05, "embedding": 0.4}, {"tfidf": 0.1, "embedding": 0.5}) is False
    assert passes({}, {"tfidf": 0.0}) is True or passes({}, {"tfidf": 0.0}) is False   # no crash on a missing component


def test_returned_pages_hide_everything_below_the_gate_and_filter_by_the_methods_own_score():
    rec = record("x", True, {"tfidf": 0.3}, [["a", 1, 0.3], ["a", 2, 0.04]], [["a", 1]])
    assert returned_pages(rec, "tfidf", {"tfidf": 0.05}) == [("a", 1)]            # low-scoring chunk filtered out
    assert returned_pages(rec, "tfidf", {"tfidf": 0.5}) == []                    # gate not cleared: abstain
    hybrid = record("x", True, {"tfidf": 0.3, "embedding": 0.2}, [["a", 1, 0.016], ["a", 2, 0.015]], [["a", 1]])
    assert returned_pages(hybrid, "hybrid", {"tfidf": 0.1, "embedding": 0.9}) == [("a", 1), ("a", 2)]   # fused scores are not filtered


def test_operating_point_counts_abstentions_and_end_to_end_recall():
    records = [
        record("a1", True, {"tfidf": 0.4}, [["d", 1, 0.4]], [["d", 1]]),                  # answered correctly
        record("a2", True, {"tfidf": 0.03}, [["d", 2, 0.03]], [["d", 2]]),                # right page, but below the gate
        record("a3", True, {"tfidf": 0.5}, [["d", 9, 0.5], ["d", 3, 0.2]], [["d", 3]]),   # relevant page at rank 2
        record("u1", False, {"tfidf": 0.02}, [["d", 7, 0.02]]),                           # correctly abstains
        record("u2", False, {"tfidf": 0.3}, [["d", 8, 0.3]]),                             # wrongly answers
    ]
    op = operating_point(records, "tfidf", {"tfidf": 0.05})
    assert op["abstention_accuracy_on_unanswerable"]["value"] == 0.5
    assert op["false_abstain_rate_on_answerable"]["value"] == pytest.approx(1 / 3, abs=1e-4)
    assert op["end_to_end_recall@1"]["value"] == pytest.approx(1 / 3, abs=1e-4)           # only a1
    assert op["end_to_end_recall@3"]["value"] == pytest.approx(2 / 3, abs=1e-4)           # a1 and a3 (rank 2)


def test_the_sweep_shows_the_tradeoff_between_abstaining_and_missing_answers():
    records = [
        record("a1", True, {"embedding": 0.8}, [["d", 1, 0.8]], [["d", 1]]),
        record("a2", True, {"embedding": 0.6}, [["d", 2, 0.6]], [["d", 2]]),
        record("u1", False, {"embedding": 0.55}, [["d", 7, 0.55]]),
        record("u2", False, {"embedding": 0.4}, [["d", 8, 0.4]]),
    ]
    rows = {r["threshold"]: r for r in sweep(records, "embedding")}
    assert rows[0.3]["correct_abstain"] == 0.0 and rows[0.3]["false_abstain"] == 0.0     # answers everything
    assert rows[0.5]["correct_abstain"] == 0.5 and rows[0.5]["false_abstain"] == 0.0     # best operating point here
    assert rows[0.7]["false_abstain"] == 0.5                                             # too strict: loses a real answer
    abstain = [rows[t]["correct_abstain"] for t in sorted(rows)]
    assert abstain == sorted(abstain)                                                    # stricter never abstains less
    assert sweep(records, "hybrid") == []


def test_the_report_breaks_results_down_by_type_and_author():
    records = [
        record("a1", True, {"tfidf": 0.4}, [["d", 1, 0.4]], [["d", 1]], **{"recall@1": 1.0, "recall@3": 1.0, "recall@5": 1.0, "rr": 1.0, "precision@3": 1.0}),
        record("a2", True, {"tfidf": 0.4}, [["d", 9, 0.4]], [["d", 2]], **{"recall@1": 0.0, "recall@3": 0.0, "recall@5": 0.0, "rr": 0.0, "precision@3": 0.0}, type="paraphrase", author="owner"),
    ]
    report = report_arm("tfidf", records, {"tfidf": 0.05})
    assert report["ranking"]["recall@3"]["value"] == 0.5
    assert report["ranking_by_type"]["paraphrase"]["recall@3"]["value"] == 0.0 and report["ranking_by_type"]["direct"]["n"] == 1
    assert report["ranking_by_author"]["owner"]["n"] == 1
    assert report["per_question"] == records


# --------------------------------------------------------------------- smoke test

@pytest.fixture
def tiny_world(monkeypatch, tmp_path):
    monkeypatch.setattr(run_module, "load_pages", lambda: PAGES)
    monkeypatch.setattr(run_module, "load_questions", lambda *paths: list(QUESTIONS))
    monkeypatch.setattr(run_module, "load_manifest", lambda: {"corpus_version": "test"})
    monkeypatch.setattr(run_module, "FastEmbedEmbedder", lambda model, cache: FakeEmbedder())
    monkeypatch.setattr(arms_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run_module, "DATA_DIR", tmp_path)


def test_tuned_thresholds_are_reported_next_to_the_current_defaults_when_available(tiny_world):
    none = run_module.run("all", ["tfidf", "embedding"], 950, 170, None, quiet=True, tuned_thresholds=None)
    assert all(a["operating_point_tuned"] is None for a in none["arms"].values())
    tuned = {"tfidf": 0.2, "embedding": 0.6}
    both = run_module.run("all", ["tfidf", "embedding", "hybrid"], 950, 170, None, quiet=True, tuned_thresholds=tuned)
    assert both["config"]["tuned_thresholds"] == tuned
    assert both["arms"]["tfidf"]["operating_point_tuned"]["thresholds"] == {"tfidf": 0.2}
    assert both["arms"]["embedding"]["operating_point_tuned"]["thresholds"] == {"embedding": 0.6}
    assert both["arms"]["hybrid"]["operating_point_tuned"]["thresholds"] == tuned     # hybrid uses both tuned thresholds
    assert both["arms"]["tfidf"]["operating_point_at_current_defaults"] is not None  # the current defaults are still shown


def test_tuned_thresholds_load_from_the_frozen_dev_file(tmp_path):
    path = tmp_path / "tuning.json"
    assert run_module.load_tuned(path) is None
    path.write_text(json.dumps({"thresholds": {"tfidf": {"chosen": 0.25}, "embedding": {"chosen": 0.7}}}))
    assert run_module.load_tuned(path) == {"tfidf": 0.25, "embedding": 0.7}


def test_a_full_run_on_a_tiny_corpus_produces_a_complete_serialisable_report(tiny_world, tmp_path):
    out = tmp_path / "report.json"
    report = run_module.run("all", ["tfidf", "embedding", "hybrid"], 950, 170, out, quiet=True)
    assert set(report["arms"]) == {"tfidf", "embedding", "hybrid"}
    assert report["questions"] == {"total": 10, "answerable": 6, "unanswerable": 4, "by_author": {"assistant": 8, "owner": 2}}
    for arm in report["arms"].values():
        assert len(arm["per_question"]) == 10 and {"recall@1", "recall@3", "recall@5", "mrr"} <= set(arm["ranking"])
    assert report["arms"]["tfidf"]["ranking"]["recall@3"]["value"] > 0                  # sanity: it finds easy answers
    assert json.loads(out.read_text())["schema"] == 1 and report["git"].keys() == {"commit", "dirty"}
    again = run_module.run("all", ["tfidf", "embedding", "hybrid"], 950, 170, None, quiet=True)
    assert without_timing(report) == without_timing(again)      # reproducible: only measured latencies may differ


def test_the_dev_and_test_splits_are_disjoint_and_the_test_split_needs_an_explicit_flag(tiny_world, tmp_path, capsys):
    dev = run_module.run("dev", ["tfidf"], 950, 170, None, quiet=True)
    test = run_module.run("test", ["tfidf"], 950, 170, None, quiet=True)
    dev_ids = {r["id"] for r in dev["arms"]["tfidf"]["per_question"]}
    test_ids = {r["id"] for r in test["arms"]["tfidf"]["per_question"]}
    assert dev_ids and test_ids and not dev_ids & test_ids
    run_module.main(["--arms", "tfidf", "--out", str(tmp_path / "x.json")])
    assert "FINAL RUN" not in capsys.readouterr().out and json.loads((tmp_path / "x.json").read_text())["split"] == "dev"
    run_module.main(["--arms", "tfidf", "--final", "--out", str(tmp_path / "y.json")])
    assert "FINAL RUN" in capsys.readouterr().out and json.loads((tmp_path / "y.json").read_text())["split"] == "test"


def test_an_invalid_dataset_stops_the_run_with_a_clear_message(tiny_world, monkeypatch):
    bad = [Question("bad", "direct", "assistant", "A perfectly fine question?", doc="alpha", answer_spans=("a phrase nobody wrote",))]
    monkeypatch.setattr(run_module, "load_questions", lambda *paths: bad)
    with pytest.raises(SystemExit) as caught:
        run_module.run("dev", ["tfidf"], 950, 170, None, quiet=True)
    assert "Dataset is invalid" in str(caught.value) and "bad" in str(caught.value)


def test_a_dataset_too_small_to_split_fails_clearly_instead_of_crashing(tiny_world, monkeypatch):
    monkeypatch.setattr(run_module, "load_questions", lambda *paths: [QUESTIONS[0]])
    with pytest.raises(SystemExit) as caught:
        run_module.run("test", ["tfidf"], 950, 170, None, quiet=True)
    assert "too small to split" in str(caught.value)
