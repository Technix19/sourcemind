import pytest

from evaluation.tune import DEFAULT_CONFIG, balanced_accuracy, choose_chunk_config, tune_threshold


def rec(answerable, best, arm="embedding"):
    return {"answerable": answerable, "gate": {arm: best}}


# answerable questions score 0.7-0.9, unanswerable ones 0.4-0.6: a clean gap between 0.6 and 0.7
CLEAN = [rec(True, s) for s in (0.7, 0.75, 0.8, 0.9)] + [rec(False, s) for s in (0.4, 0.5, 0.55, 0.6)]


def test_balanced_accuracy_weights_both_kinds_of_error_equally():
    low = balanced_accuracy(CLEAN, "embedding", 0.3)     # answers everything
    assert low["correct_abstain"] == 0.0 and low["false_abstain"] == 0.0 and low["balanced_accuracy"] == 0.5
    perfect = balanced_accuracy(CLEAN, "embedding", 0.65)
    assert perfect["balanced_accuracy"] == 1.0
    strict = balanced_accuracy(CLEAN, "embedding", 0.95)  # refuses everything
    assert strict["correct_abstain"] == 1.0 and strict["false_abstain"] == 1.0 and strict["balanced_accuracy"] == 0.5


def test_the_threshold_is_inclusive():
    assert balanced_accuracy([rec(True, 0.5)], "embedding", 0.5)["false_abstain"] == 0.0
    assert balanced_accuracy([rec(True, 0.5)], "embedding", 0.51)["false_abstain"] == 1.0


def test_tuning_finds_the_gap_and_picks_the_middle_of_the_plateau():
    t = tune_threshold(CLEAN, "embedding")
    assert t["balanced_accuracy"] == 1.0
    assert t["tied_thresholds"] == [0.61, 0.7]                        # every value from just above 0.60 up to 0.70
    assert t["chosen"] == 0.65 and t["at_chosen"]["balanced_accuracy"] == 1.0   # the middle, not an edge


def test_a_single_best_threshold_is_chosen_directly():
    records = [rec(True, 0.9), rec(True, 0.5), rec(False, 0.45)]
    t = tune_threshold(records, "embedding", grid=[0.4, 0.46, 0.6])
    assert t["chosen"] == 0.46 and t["balanced_accuracy"] == 1.0 and t["tied_thresholds"] == [0.46, 0.46]


def test_with_no_good_threshold_it_reports_honestly_how_poor_the_best_is():
    overlapping = [rec(True, 0.5), rec(False, 0.5), rec(True, 0.6), rec(False, 0.6)]
    assert tune_threshold(overlapping, "embedding")["balanced_accuracy"] <= 0.75


def test_tuning_only_looks_at_the_requested_method():
    records = [{"answerable": True, "gate": {"tfidf": 0.9, "embedding": 0.1}}, {"answerable": False, "gate": {"tfidf": 0.1, "embedding": 0.9}}]
    assert tune_threshold(records, "tfidf", grid=[0.5])["balanced_accuracy"] == 1.0
    assert tune_threshold(records, "embedding", grid=[0.5])["balanced_accuracy"] == 0.0


# ------------------------------------------------------------- chunk-size rule

def results(**by_size):
    base = {(950, 170): {"recall@3": 0.70, "mrr": 0.60}}
    for size, (recall, mrr) in by_size.items():
        base[(int(size[1:]), 0)] = {"recall@3": recall, "mrr": mrr}
    return base


def test_the_default_is_kept_unless_another_size_wins_on_both_metrics_by_the_margin():
    assert choose_chunk_config(results(s500=(0.75, 0.65)))[0] == DEFAULT_CONFIG          # +0.05: not enough
    assert choose_chunk_config(results(s500=(0.85, 0.65)))[0] == DEFAULT_CONFIG          # recall wins, MRR does not
    assert choose_chunk_config(results(s500=(0.85, 0.75)))[0] == (500, 0)                # both win by >= 0.10
    assert choose_chunk_config(results(s500=(0.80, 0.70)))[0] == (500, 0)                # exactly at the margin counts


def test_the_best_qualifying_size_is_chosen_and_notes_are_explained():
    chosen, notes = choose_chunk_config(results(s500=(0.82, 0.72), s1500=(0.95, 0.85)))
    assert chosen == (1500, 0) and len(notes) == 2 and "Recall@3 +0.25" in notes[1]
