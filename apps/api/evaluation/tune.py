"""Development-split tuning, exactly as pre-registered in docs/m7-design.md.

    python -m evaluation.tune            # chunk-size experiment, then thresholds at the chosen size (dev split only)

Nothing here ever looks at the test split.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .corpus import DATA_DIR
from .run import run
from .metrics import summarize

CHUNK_CONFIGS = [(500, 90), (950, 170), (1500, 270)]     # characters; overlap about 18%
DEFAULT_CONFIG = (950, 170)
MIN_GAIN = 0.10                                          # pre-registered: must beat the default on BOTH metrics by this much
GRIDS = {
    "tfidf": [round(i * 0.01, 2) for i in range(0, 41)],
    "embedding": [round(0.40 + i * 0.01, 2) for i in range(0, 51)],
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def balanced_accuracy(records: list[dict], arm: str, threshold: float) -> dict:
    """Mean of (correct abstention on unanswerable) and (1 - false abstention on answerable), at one threshold."""
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]
    answers = lambda r: r["gate"].get(arm, 0.0) >= threshold      # does the method return anything?
    correct_abstain = _mean([0.0 if answers(r) else 1.0 for r in unanswerable])
    false_abstain = _mean([0.0 if answers(r) else 1.0 for r in answerable])
    return {"threshold": threshold, "correct_abstain": correct_abstain, "false_abstain": false_abstain,
            "balanced_accuracy": (correct_abstain + (1.0 - false_abstain)) / 2}


def tune_threshold(records: list[dict], arm: str, grid: list[float] | None = None) -> dict:
    """Pick the threshold with the best balanced accuracy; ties resolve to the MEDIAN of the tied values."""
    grid = grid if grid is not None else GRIDS[arm]
    curve = [balanced_accuracy(records, arm, t) for t in grid]
    best = max(row["balanced_accuracy"] for row in curve)
    tied = [row["threshold"] for row in curve if abs(row["balanced_accuracy"] - best) < 1e-9]
    chosen = tied[(len(tied) - 1) // 2]
    return {"chosen": chosen, "balanced_accuracy": round(best, 4), "tied_thresholds": [min(tied), max(tied)],
            "at_chosen": next(row for row in curve if row["threshold"] == chosen), "curve": curve}


def choose_chunk_config(results: dict[tuple[int, int], dict]) -> tuple[tuple[int, int], list[str]]:
    """Pre-registered rule: keep the default unless another size beats it on BOTH Recall@3 and MRR by MIN_GAIN.

    `results` maps (size, overlap) to {"recall@3": float, "mrr": float} for the method being judged.
    """
    base = results[DEFAULT_CONFIG]
    notes = []
    winners = []
    for config, m in results.items():
        if config == DEFAULT_CONFIG:
            continue
        # Rounded, because 0.70 - 0.60 is 0.0999999... in floating point and must still count as 0.10.
        gains = (round(m["recall@3"] - base["recall@3"], 6), round(m["mrr"] - base["mrr"], 6))
        notes.append(f"{config[0]}: Recall@3 {gains[0]:+.2f}, MRR {gains[1]:+.2f} vs the default")
        if gains[0] >= MIN_GAIN and gains[1] >= MIN_GAIN:
            winners.append((min(gains), config))
    return (max(winners)[1] if winners else DEFAULT_CONFIG), notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DATA_DIR / "results" / "tuning-dev.json")
    args = parser.parse_args(argv)

    print("Chunk-size experiment (DEV split only)\n")
    by_config: dict[tuple[int, int], dict] = {}
    for size, overlap in CHUNK_CONFIGS:
        print(f"  size={size} overlap={overlap} ...")
        by_config[(size, overlap)] = run("dev", ["tfidf", "embedding", "hybrid"], size, overlap, None, quiet=True)
    table = {}
    print(f"\n{'size':>6} {'chunks':>7}  " + "  ".join(f"{a:>26}" for a in ("tfidf", "embedding", "hybrid")))
    print(f"{'':>6} {'':>7}  " + "  ".join(f"{'Recall@3':>12} {'MRR':>13}" for _ in range(3)))
    for (size, overlap), report in by_config.items():
        cells, table[f"{size}/{overlap}"] = [], {"chunks": report["config"]["chunks"]}
        for arm in ("tfidf", "embedding", "hybrid"):
            r = report["arms"][arm]["ranking"]
            table[f"{size}/{overlap}"][arm] = {"recall@3": r["recall@3"], "mrr": r["mrr"]}
            cells.append(f"{r['recall@3']['value']:12.2f} {r['mrr']['value']:13.2f}")
        print(f"{size:>6} {report['config']['chunks']:>7}  " + "  ".join(cells))

    decisions = {}
    for arm in ("tfidf", "embedding"):
        metrics = {cfg: {"recall@3": rep["arms"][arm]["ranking"]["recall@3"]["value"], "mrr": rep["arms"][arm]["ranking"]["mrr"]["value"]}
                   for cfg, rep in by_config.items()}
        chosen, notes = choose_chunk_config(metrics)
        decisions[arm] = {"chosen": chosen, "notes": notes}
    both = {d["chosen"] for d in decisions.values()}
    chosen = DEFAULT_CONFIG if len(both) != 1 else both.pop()     # the two methods share one chunking, so they must agree
    print(f"\nChunk config chosen by the pre-registered rule: size={chosen[0]} overlap={chosen[1]}")
    for arm, d in decisions.items():
        print(f"  {arm}: " + "; ".join(d["notes"]))

    records = {arm: by_config[chosen]["arms"][arm]["per_question"] for arm in ("tfidf", "embedding")}
    tuned = {arm: tune_threshold(records[arm], arm) for arm in ("tfidf", "embedding")}
    print("\nThresholds tuned on DEV (balanced accuracy; ties -> median):")
    for arm, t in tuned.items():
        a = t["at_chosen"]
        print(f"  {arm:10} threshold={t['chosen']:.2f}  (tied range {t['tied_thresholds'][0]:.2f}-{t['tied_thresholds'][1]:.2f})  "
              f"correct abstention {a['correct_abstain']:.2f}  false abstention {a['false_abstain']:.2f}  balanced accuracy {t['balanced_accuracy']:.2f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "schema": 1, "split": "dev", "note": "Development split only. Produced by evaluation.tune following the plan pre-registered in docs/m7-design.md.",
        "chunk_experiment": table, "chunk_config_chosen": {"size": chosen[0], "overlap": chosen[1], "per_method_notes": decisions},
        "thresholds": {arm: {k: v for k, v in t.items() if k != "curve"} for arm, t in tuned.items()},
        "threshold_curves": {arm: [{k: round(v, 4) for k, v in row.items()} for row in t["curve"]] for arm, t in tuned.items()},
    }, indent=2, default=list) + "\n")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
