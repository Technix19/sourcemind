"""Turn a final evaluation run into what the app and the README show.

    python -m evaluation.publish results/final-test-2026-11-04.json

Writes data/evaluation/results/latest.json (served by the API) and REPORT.md. It adds no numbers:
every figure is copied from the run, and the recommendation is computed by the pre-registered rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .corpus import DATA_DIR

RESULTS = DATA_DIR / "results"
LABELS = {"tfidf": "Keyword (TF-IDF)", "embedding": "Meaning (embeddings)", "hybrid": "Hybrid (experimental)"}
NOT_MEASURED = [
    "Citation accuracy and faithfulness of generated answers (needs a language-model key; retrieval only is measured here).",
    "Production latency: the figures here exclude network and database time, and the product refits keyword search per query.",
    "Different document types, languages, scanned PDFs, or very large libraries.",
]


def balanced_accuracy(op: dict | None) -> float | None:
    if not op:
        return None
    return round((op["abstention_accuracy_on_unanswerable"]["value"] + 1.0 - op["false_abstain_rate_on_answerable"]["value"]) / 2, 4)


def separated(a: dict, b: dict) -> bool:
    """True only if the 95% intervals do not overlap or touch (the pre-registered standard for 'different')."""
    return a["ci"][0] > b["ci"][1] or b["ci"][0] > a["ci"][1]


def recommend(arms: dict) -> dict:
    """Pre-registered rule 3. The default stays keyword; a change is only RECOMMENDED when a method has higher
    point estimates for Recall@3 and MRR and a balanced accuracy at its tuned threshold that is not lower."""
    base = arms["tfidf"]
    base_ba = balanced_accuracy(base["operating_point_tuned"])
    candidates = []
    for name in ("embedding", "hybrid"):
        a = arms.get(name)
        if not a:
            continue
        r, b = a["ranking"], base["ranking"]
        ba = balanced_accuracy(a["operating_point_tuned"])
        condition = (r["recall@3"]["value"] > b["recall@3"]["value"] and r["mrr"]["value"] > b["mrr"]["value"]
                     and ba is not None and base_ba is not None and ba >= base_ba)
        demonstrated = separated(r["recall@3"], b["recall@3"]) or separated(r["mrr"], b["mrr"])
        candidates.append({"method": name, "condition_met": condition, "difference_demonstrated": demonstrated, "balanced_accuracy": ba})
    met = [c for c in candidates if c["condition_met"]]
    if not met:
        text = "Keep keyword search as the default. No other method met the pre-registered condition."
    elif any(c["difference_demonstrated"] for c in met):
        text = "A change of default is supported: the better method's interval is separated from keyword search on a pre-registered metric."
    else:
        names = " and ".join(LABELS[c["method"]] for c in met)
        text = (f"{names} met the pre-registered condition for RECOMMENDING a change of default (higher Recall@3 and MRR, balanced accuracy not lower), "
                "but no difference is demonstrated: the 95% intervals overlap. This is a judgment call for the project owner, not a measured win.")
    return {"rule": "docs/m7-design.md, pre-registered rule 3", "keyword_balanced_accuracy": base_ba, "candidates": candidates, "text": text}


def trim_question(rec: dict) -> dict:
    keep = {k: rec[k] for k in ("id", "type", "author", "question", "answerable", "gate") if k in rec}
    keep["top"] = rec["ranked"][:3]
    if rec["answerable"]:
        keep["rank"], keep["relevant"] = rec["rank"], rec["relevant"]
    return keep


def caveats(report: dict) -> list[str]:
    q = report["questions"]
    return [
        f"Small sample: {q['answerable']} answerable and {q['unanswerable']} unanswerable test questions. Every figure has a wide 95% interval; overlapping intervals mean no demonstrated difference.",
        "A single author wrote all questions (the project assistant); there is no independent-author check, and wording bias toward keyword search cannot be ruled out.",
        "Five public-domain US government documents; the results may not transfer to other kinds of documents.",
        "The test split was scored once, after the thresholds and chunk size were frozen on the development split (see the pre-registered plan).",
        "An interval such as 1.00 (1.00-1.00) is NOT certainty: a percentile bootstrap collapses to a point whenever every question agrees, which with only a handful of questions says little. The true uncertainty is larger (this is most visible in the abstention rows, which rest on 4 questions).",
        "Retrieval only: this measures whether the right page is found, not whether generated answers are correct.",
    ]


def build_latest(report: dict, tuning: dict, analysis: dict) -> dict:
    arms = report["arms"]
    methods = {}
    for name, a in arms.items():
        methods[name] = {
            "label": LABELS[name], "ranking": a["ranking"], "ranking_by_type": a["ranking_by_type"], "ranking_by_author": a["ranking_by_author"],
            "operating_point_tuned": a["operating_point_tuned"], "operating_point_at_product_defaults": a["operating_point_at_current_defaults"],
            "balanced_accuracy_tuned": balanced_accuracy(a["operating_point_tuned"]),
            "threshold_sweep": a["threshold_sweep"], "latency_ms": a["latency_ms"],
            "per_question": [trim_question(r) for r in a["per_question"]],
        }
    return {
        "schema": 1,
        "run": {"split": report["split"], "date": report["date"], "git": report["git"], "dataset_version": report["dataset_version"],
                "corpus_version": report["corpus_version"], "questions": report["questions"],
                "chunks": report["config"]["chunks"], "chunk_size": report["config"]["chunk_size"], "overlap": report["config"]["overlap"],
                "embedding_model": report["config"]["embedding_model"]},
        "thresholds": {"tuned": report["config"]["tuned_thresholds"], "product_defaults": report["config"]["provisional_thresholds"],
                       "tuned_on": "dev split",
                       "tuning": {arm: {"tied_range": t["tied_thresholds"], "dev_balanced_accuracy": t["balanced_accuracy"]} for arm, t in tuning["thresholds"].items()}},
        "caveats": caveats(report),
        "methods": methods,
        "product_keyword_latency_ms": report["product_tfidf_latency_ms"],
        "chunk_experiment": {"split": "dev", "chosen": tuning["chunk_config_chosen"]["size"], "rows": tuning["chunk_experiment"]},
        "recommendation": recommend(arms),
        "analysis": analysis,
        "not_measured": NOT_MEASURED,
    }


def fmt(s: dict | None) -> str:
    return "n/a" if not s or s["value"] is None else f"{s['value']:.2f} ({s['ci'][0]:.2f}-{s['ci'][1]:.2f})"


def build_report(latest: dict) -> str:
    run, m = latest["run"], latest["methods"]
    q = run["questions"]
    lines = [
        "# Retrieval evaluation report", "",
        f"Held-out **{run['split']}** split, scored once on {run['date']} at commit `{run['git']['commit']}` "
        f"({'clean working tree' if not run['git']['dirty'] else 'DIRTY working tree'}). "
        f"{q['total']} questions ({q['answerable']} answerable, {q['unanswerable']} unanswerable); {run['chunks']} chunks of {run['chunk_size']} characters.", "",
        "Values are means with 95% bootstrap intervals in parentheses. **If two intervals overlap, no difference is demonstrated.**", "",
        "## Read this first", "", *[f"- {c}" for c in latest["caveats"]], "",
        "## Ranking quality (threshold-free)", "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | MRR |", "|---|---|---|---|---|",
    ]
    for name, x in m.items():
        r = x["ranking"]
        lines.append(f"| {x['label']} | {fmt(r['recall@1'])} | {fmt(r['recall@3'])} | {fmt(r['recall@5'])} | {fmt(r['mrr'])} |")
    types = sorted({t for x in m.values() for t in x["ranking_by_type"]})
    lines += ["", "### Recall@3 by question type", "", "| Type | " + " | ".join(x["label"] for x in m.values()) + " |", "|---|" + "---|" * len(m)]
    for t in types:
        lines.append(f"| {t} (n={next(iter(m.values()))['ranking_by_type'][t]['n']}) | " + " | ".join(fmt(x["ranking_by_type"][t]["recall@3"]) for x in m.values()) + " |")
    lines += ["", "## Saying \"not enough evidence\"", "",
              f"Thresholds were tuned on the development split: keyword **{latest['thresholds']['tuned']['tfidf']}**, meaning **{latest['thresholds']['tuned']['embedding']}**. "
              f"The product's current defaults are {latest['thresholds']['product_defaults']['tfidf']} and {latest['thresholds']['product_defaults']['embedding']}. "
              f"Only {q['unanswerable']} unanswerable test questions exist, so abstention intervals are very wide.", "",
              "| Method | Setting | Correct abstention | False abstention | End-to-end Recall@3 |", "|---|---|---|---|---|"]
    for name, x in m.items():
        for label, key in (("tuned", "operating_point_tuned"), ("product defaults", "operating_point_at_product_defaults")):
            o = x[key]
            if o:
                lines.append(f"| {x['label']} | {label} | {fmt(o['abstention_accuracy_on_unanswerable'])} | {fmt(o['false_abstain_rate_on_answerable'])} | {fmt(o['end_to_end_recall@3'])} |")
    lines += ["", "## Recommendation", "", latest["recommendation"]["text"], "",
              "## Chunk size (development split)", "", "| Size / overlap | Chunks | Keyword Recall@3 | Meaning Recall@3 |", "|---|---|---|---|"]
    for key, row in latest["chunk_experiment"]["rows"].items():
        lines.append(f"| {key} | {row['chunks']} | {fmt(row['tfidf']['recall@3'])} | {fmt(row['embedding']['recall@3'])} |")
    lines += ["", f"The pre-registered rule keeps {latest['chunk_experiment']['chosen']} characters unless another size wins on both Recall@3 and MRR by at least 0.10; none did.", "",
              "## Failure analysis", "", latest["analysis"]["note"], ""]
    for p in latest["analysis"]["patterns"]:
        lines += [f"### {p['title']}", "", p["evidence"], ""]
    lines += ["### Label limitations", ""] + [f"- **{x['id']}**: {x['explanation']}" for x in latest["analysis"]["label_limitations"]] + ["", "### Individual misses (rank of the first correct page)", ""]
    for x in latest["analysis"]["misses"]:
        ranks = ", ".join(f"{k} {v}" for k, v in x["ranks"].items())
        lines.append(f"- **{x['id']}** ({x['category'].replace('_', ' ')}; {ranks}): {x['explanation']}")
    lines += ["", "## Not measured", "", *[f"- {n}" for n in latest["not_measured"]], ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    source = Path(argv[0] if argv else sys.argv[1])
    source = source if source.is_absolute() else (RESULTS / source if not source.exists() else source)
    report = json.loads(source.read_text())
    if report["split"] != "test":
        raise SystemExit("Only a run of the held-out TEST split can be published.")
    latest = build_latest(report, json.loads((RESULTS / "tuning-dev.json").read_text()), json.loads((DATA_DIR / "failure_analysis.json").read_text()))
    (RESULTS / "latest.json").write_text(json.dumps(latest, indent=2) + "\n")
    (RESULTS / "REPORT.md").write_text(build_report(latest))
    print(f"wrote {RESULTS / 'latest.json'} and {RESULTS / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
