import math

import pytest

from evaluation.metrics import (
    bootstrap_ci, first_relevant_rank, percentile, precision_at_k, recall_at_k, reciprocal_rank, summarize,
)

REL = {("d", 2), ("d", 5)}


def test_first_relevant_rank_is_one_based_and_none_when_absent():
    assert first_relevant_rank([("d", 9), ("d", 2), ("d", 5)], REL) == 2
    assert first_relevant_rank([("d", 2)], REL) == 1
    assert first_relevant_rank([("d", 9), ("x", 2)], REL) is None      # same page number, other document: not relevant
    assert first_relevant_rank([], REL) is None


def test_recall_at_k_is_a_per_question_hit():
    assert [recall_at_k(r, 3) for r in (1, 3, 4, None)] == [1.0, 1.0, 0.0, 0.0]
    assert recall_at_k(1, 1) == 1.0 and recall_at_k(2, 1) == 0.0


def test_reciprocal_rank():
    assert [reciprocal_rank(r) for r in (1, 2, 4, None)] == [1.0, 0.5, 0.25, 0.0]


def test_precision_at_k_counts_returned_chunks_not_requested_slots():
    pages = [("d", 2), ("d", 9), ("d", 5)]
    assert precision_at_k(pages, REL, 3) == pytest.approx(2 / 3)
    assert precision_at_k(pages, REL, 1) == 1.0
    assert precision_at_k(pages[:2], REL, 5) == pytest.approx(1 / 2)   # only two were returned
    assert precision_at_k([], REL, 3) == 0.0


def test_percentile_nearest_rank():
    data = [10, 20, 30, 40, 50]
    assert percentile(data, 50) == 30 and percentile(data, 100) == 50 and percentile(data, 20) == 10
    assert percentile([], 50) is None
    assert percentile([7], 95) == 7


def test_bootstrap_interval_is_deterministic_and_brackets_the_mean():
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0]
    lo, hi = bootstrap_ci(values)
    assert (lo, hi) == bootstrap_ci(values)                           # same seed, same answer
    assert lo <= sum(values) / len(values) <= hi and 0.0 <= lo < hi <= 1.0


def test_bootstrap_interval_collapses_when_everything_agrees_and_widens_with_noise():
    assert bootstrap_ci([1.0] * 12) == (1.0, 1.0)
    assert bootstrap_ci([0.0] * 12) == (0.0, 0.0)
    tight = bootstrap_ci([1.0] * 18 + [0.0] * 2)
    wide = bootstrap_ci([1.0] * 5 + [0.0] * 5)
    assert (wide[1] - wide[0]) > (tight[1] - tight[0])


def test_more_data_gives_a_narrower_interval():
    small = bootstrap_ci([1.0, 0.0] * 5)
    large = bootstrap_ci([1.0, 0.0] * 50)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_empty_input_is_nan_not_a_crash():
    lo, hi = bootstrap_ci([])
    assert math.isnan(lo) and math.isnan(hi)
    assert summarize([]) == {"value": None, "ci": None, "n": 0}


def test_summarize_reports_mean_interval_and_sample_size():
    s = summarize([1.0, 1.0, 0.0, 1.0])
    assert s["value"] == 0.75 and s["n"] == 4 and s["ci"][0] <= 0.75 <= s["ci"][1]
