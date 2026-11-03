"""Metrics and uncertainty. Pure functions, no I/O.

With a few dozen questions a single number is not evidence: every summary here carries a
bootstrap confidence interval, and callers should treat overlapping intervals as 'no demonstrated difference'.
"""
from __future__ import annotations

import random
from statistics import mean


def bootstrap_ci(values: list[float], *, n_boot: int = 2000, seed: int = 7, level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean (resampling questions with replacement)."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(n_boot))
    lo = means[int((1 - level) / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 + level) / 2 * n_boot))]
    return (lo, hi)


def summarize(values: list[float]) -> dict:
    """{'value': mean, 'ci': [lo, hi], 'n': count}; value is None when there is nothing to average."""
    if not values:
        return {"value": None, "ci": None, "n": 0}
    lo, hi = bootstrap_ci(values)
    return {"value": round(mean(values), 4), "ci": [round(lo, 4), round(hi, 4)], "n": len(values)}


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0..100)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-int(p * len(ordered)) // 100)) if p < 100 else len(ordered)
    return ordered[min(rank, len(ordered)) - 1]


def first_relevant_rank(pages: list[tuple[str, int]], relevant: set[tuple[str, int]]) -> int | None:
    """1-based rank of the first returned chunk whose (doc, page) is relevant, else None."""
    for rank, page in enumerate(pages, start=1):
        if page in relevant:
            return rank
    return None


def recall_at_k(rank: int | None, k: int) -> float:
    """1.0 if a relevant chunk is in the top k (the blueprint's definition, per question), else 0.0."""
    return 1.0 if rank is not None and rank <= k else 0.0


def reciprocal_rank(rank: int | None) -> float:
    return 1.0 / rank if rank else 0.0


def precision_at_k(pages: list[tuple[str, int]], relevant: set[tuple[str, int]], k: int) -> float:
    """Share of the top k returned chunks that are relevant (0 when nothing is returned)."""
    top = pages[:k]
    return sum(1 for p in top if p in relevant) / len(top) if top else 0.0
