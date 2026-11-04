import json

import pytest

from evaluation import publish
from evaluation.corpus import DATA_DIR
from evaluation.publish import balanced_accuracy, recommend, separated, trim_question


def s(value, lo, hi, n=15):
    return {"value": value, "ci": [lo, hi], "n": n}


def op(correct, false):
    return {"abstention_accuracy_on_unanswerable": s(correct, 0, 1, 4), "false_abstain_rate_on_answerable": s(false, 0, 1)}


def arm(recall3, mrr, correct=0.5, false=0.2, r3ci=(0.3, 0.8), mrrci=(0.3, 0.8)):
    return {"ranking": {"recall@3": s(recall3, *r3ci), "mrr": s(mrr, *mrrci)}, "operating_point_tuned": op(correct, false)}


def test_balanced_accuracy_averages_correct_abstention_and_not_refusing_valid_questions():
    assert balanced_accuracy(op(1.0, 0.67)) == pytest.approx((1.0 + 0.33) / 2, abs=1e-4)
    assert balanced_accuracy(op(0.5, 0.13)) == pytest.approx(0.685, abs=1e-3)
    assert balanced_accuracy(None) is None


def test_intervals_that_merely_touch_are_not_separated():
    assert separated(s(0.9, 0.80, 1.0), s(0.5, 0.2, 0.7)) is True
    assert separated(s(0.9, 0.80, 1.0), s(0.6, 0.3, 0.80)) is False      # touching at 0.80: not demonstrated
    assert separated(s(0.9, 0.5, 1.0), s(0.6, 0.3, 0.7)) is False


def test_no_recommendation_unless_recall_mrr_and_balanced_accuracy_all_hold():
    base = arm(0.60, 0.50, correct=1.0, false=0.67)                      # balanced accuracy 0.665
    better_but_worse_abstention = arm(0.87, 0.75, correct=0.0, false=0.0, r3ci=(0.6, 1.0))   # 0.5 < 0.665
    out = recommend({"tfidf": base, "embedding": better_but_worse_abstention})
    assert out["candidates"][0]["condition_met"] is False and out["text"].startswith("Keep keyword search")
    lower_recall = arm(0.50, 0.75, correct=1.0, false=0.0)
    assert recommend({"tfidf": base, "embedding": lower_recall})["candidates"][0]["condition_met"] is False
    lower_mrr = arm(0.87, 0.40, correct=1.0, false=0.0)                  # better Recall@3 and abstention, WORSE MRR
    assert recommend({"tfidf": base, "embedding": lower_mrr})["candidates"][0]["condition_met"] is False


def test_a_recommendation_with_overlapping_intervals_is_labeled_a_judgment_call_not_a_win():
    base = arm(0.60, 0.53, correct=1.0, false=0.67, r3ci=(0.33, 0.80), mrrci=(0.35, 0.73))
    meaning = arm(0.87, 0.75, correct=0.5, false=0.13, r3ci=(0.67, 1.0), mrrci=(0.57, 0.90))
    out = recommend({"tfidf": base, "embedding": meaning})
    assert out["candidates"][0]["condition_met"] and not out["candidates"][0]["difference_demonstrated"]
    assert "judgment call" in out["text"] and "not a measured win" in out["text"] and "intervals overlap" in out["text"]


def test_a_change_is_only_called_supported_when_intervals_really_separate():
    base = arm(0.40, 0.30, correct=0.5, false=0.2, r3ci=(0.2, 0.55), mrrci=(0.15, 0.45))
    meaning = arm(0.95, 0.90, correct=0.5, false=0.1, r3ci=(0.85, 1.0), mrrci=(0.8, 1.0))
    out = recommend({"tfidf": base, "embedding": meaning})
    assert out["candidates"][0]["difference_demonstrated"] and "supported" in out["text"]


def test_published_questions_keep_only_what_the_page_needs():
    rec = {"id": "q", "type": "direct", "author": "assistant", "question": "?", "answerable": True, "gate": {"tfidf": 0.2}, "latency_ms": 3.3,
           "ranked": [["d", i, 0.1] for i in range(1, 10)], "rank": 2, "relevant": [["d", 2]], "recall@1": 0.0, "rr": 0.5}
    out = trim_question(rec)
    assert set(out) == {"id", "type", "author", "question", "answerable", "gate", "top", "rank", "relevant"} and len(out["top"]) == 3


def test_only_the_held_out_test_split_can_be_published(tmp_path):
    dev = tmp_path / "dev.json"
    dev.write_text(json.dumps({"split": "dev"}))
    with pytest.raises(SystemExit) as caught:
        publish.main([str(dev)])
    assert "TEST split" in str(caught.value)


# ----------------------------------------------- the real published files (if they exist)

RESULTS = DATA_DIR / "results"
needs_results = pytest.mark.skipif(not (RESULTS / "latest.json").exists(), reason="results not published yet")


@needs_results
def test_published_numbers_equal_the_run_they_came_from():
    latest = json.loads((RESULTS / "latest.json").read_text())
    source = json.loads(next(RESULTS.glob("final-test-*.json")).read_text())
    assert latest["run"]["split"] == "test" == source["split"]
    for name, arm_data in source["arms"].items():
        assert latest["methods"][name]["ranking"] == arm_data["ranking"]
        assert latest["methods"][name]["operating_point_tuned"] == arm_data["operating_point_tuned"]


@needs_results
def test_published_results_carry_the_caveats_and_the_provenance():
    latest = json.loads((RESULTS / "latest.json").read_text())
    text = " ".join(latest["caveats"])
    assert "single author" in text.lower() and "Small sample" in text and "NOT certainty" in text
    assert latest["run"]["git"]["commit"] and latest["run"]["git"]["dirty"] is False   # scored from a clean, committed tree
    assert latest["analysis"]["note"].startswith("Written AFTER the held-out test split")
    assert (RESULTS / "REPORT.md").read_text().startswith("# Retrieval evaluation report")
