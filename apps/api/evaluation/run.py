"""Run the retrieval evaluation.

    python -m evaluation.run                 # development split (the default): safe to look at while building
    python -m evaluation.run --final         # held-out TEST split: run once, after every choice is frozen

Everything is measured on the same chunks the product would create from the same PDFs.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.embeddings import FastEmbedEmbedder
from app.retrieval import SearchChunk, retrieve

from .arms import POOL, EmbeddingArm, HybridArm, TfidfArm, embed_corpus
from .corpus import DATA_DIR, QUESTION_FILES, build_chunks, load_manifest, load_pages
from .dataset import Question, load_questions, normalized_pages, relevant_pages, split, validate
from .metrics import first_relevant_rank, percentile, precision_at_k, recall_at_k, reciprocal_rank, summarize

KS = (1, 3, 5)
STORED = 20   # ranked results kept per question, so thresholds can be re-applied without re-searching
GRIDS = {
    "tfidf": [0.0, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3],
    "embedding": [0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75],
}


def provisional_thresholds() -> dict[str, float]:
    s = get_settings()
    return {"tfidf": s.min_relevance_score, "embedding": s.min_embedding_score}


# ------------------------------------------------------------------------------ per question

def evaluate_question(arm, q: Question, norm) -> dict:
    result = arm.search(q.question, POOL)
    pages = [(r.chunk.doc_id, r.chunk.page) for r in result.ranked]
    record = {
        "id": q.id, "type": q.type, "author": q.author, "answerable": q.answerable, "question": q.question,
        "gate": {k: round(v, 4) for k, v in result.gate.items()}, "latency_ms": round(result.latency_ms, 3),
        "ranked": [[r.chunk.doc_id, r.chunk.page, round(r.score, 4)] for r in result.ranked[:STORED]],
    }
    if q.answerable:
        rel = relevant_pages(q, norm)
        rank = first_relevant_rank(pages, rel)
        record |= {
            "relevant": sorted([d, p] for d, p in rel), "rank": rank,
            **{f"recall@{k}": recall_at_k(rank, k) for k in KS},
            "rr": reciprocal_rank(rank), "precision@3": precision_at_k(pages, rel, 3),
        }
    return record


# ------------------------------------------------------------------------------ operating point

def passes(gate: dict[str, float], thr: dict[str, float]) -> bool:
    """Does the method return anything at these thresholds? (any component clearing its threshold)"""
    return any(gate.get(c, 0.0) >= t for c, t in thr.items())


def returned_pages(record: dict, arm_name: str, thr: dict[str, float]) -> list[tuple[str, int]]:
    """What the user would see: nothing below the gate; for single methods only chunks scoring >= threshold."""
    if not passes(record["gate"], thr):
        return []
    rows = record["ranked"]
    if arm_name in thr:                      # tfidf / embedding: filter by that method's own score
        rows = [r for r in rows if r[2] >= thr[arm_name]]
    return [(d, p) for d, p, _ in rows]


def operating_point(records: list[dict], arm_name: str, thr: dict[str, float]) -> dict:
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]
    rel = {r["id"]: {tuple(x) for x in r["relevant"]} for r in answerable}
    e2e = {k: [] for k in KS}
    false_abstain = []
    for r in answerable:
        shown = returned_pages(r, arm_name, thr)
        false_abstain.append(0.0 if shown else 1.0)
        rank = first_relevant_rank(shown, rel[r["id"]])
        for k in KS:
            e2e[k].append(recall_at_k(rank, k))
    correct_abstain = [0.0 if returned_pages(r, arm_name, thr) else 1.0 for r in unanswerable]
    by_type = {}
    for t in sorted({r["type"] for r in unanswerable}):
        by_type[t] = summarize([0.0 if returned_pages(r, arm_name, thr) else 1.0 for r in unanswerable if r["type"] == t])
    return {
        "thresholds": thr,
        "abstention_accuracy_on_unanswerable": summarize(correct_abstain),
        "false_abstain_rate_on_answerable": summarize(false_abstain),
        "abstention_by_unanswerable_type": by_type,
        **{f"end_to_end_recall@{k}": summarize(e2e[k]) for k in KS},
    }


def sweep(records: list[dict], arm_name: str) -> list[dict]:
    if arm_name not in GRIDS:
        return []
    rows = []
    for t in GRIDS[arm_name]:
        op = operating_point(records, arm_name, {arm_name: t})
        rows.append({
            "threshold": t,
            "correct_abstain": op["abstention_accuracy_on_unanswerable"]["value"],
            "false_abstain": op["false_abstain_rate_on_answerable"]["value"],
            "end_to_end_recall@3": op["end_to_end_recall@3"]["value"],
        })
    return rows


# --------------------------------------------------------------------------------- aggregate

def report_arm(arm_name: str, records: list[dict], thr: dict[str, float]) -> dict:
    answerable = [r for r in records if r["answerable"]]
    ranking = {f"recall@{k}": summarize([r[f"recall@{k}"] for r in answerable]) for k in KS}
    ranking["mrr"] = summarize([r["rr"] for r in answerable])
    ranking["precision@3"] = summarize([r["precision@3"] for r in answerable])
    by_type = {}
    for t in sorted({r["type"] for r in answerable}):
        sub = [r for r in answerable if r["type"] == t]
        by_type[t] = {"n": len(sub), "recall@3": summarize([r["recall@3"] for r in sub]), "mrr": summarize([r["rr"] for r in sub])}
    by_author = {}
    for a in sorted({r["author"] for r in answerable}):
        sub = [r for r in answerable if r["author"] == a]
        by_author[a] = {"n": len(sub), "recall@3": summarize([r["recall@3"] for r in sub]), "mrr": summarize([r["rr"] for r in sub])}
    latencies = [r["latency_ms"] for r in records]
    return {
        "ranking": ranking, "ranking_by_type": by_type, "ranking_by_author": by_author,
        "operating_point_at_current_defaults": operating_point(records, arm_name, thr),
        "threshold_sweep": sweep(records, arm_name),
        "latency_ms": {"median": percentile(latencies, 50), "p95": percentile(latencies, 95)},
        "per_question": records,
    }


def product_tfidf_latency(chunks, questions: list[Question]) -> dict:
    """What the PRODUCT pays for keyword search: it refits TF-IDF per query (measured here on the full corpus)."""
    search_chunks = [SearchChunk(f"{c.doc_id}-{c.page}-{c.index}", c.doc_id, c.doc_id, c.page, c.text) for c in chunks]
    times = []
    for q in questions[:6]:
        started = time.perf_counter()
        retrieve(q.question, search_chunks, top_k=4, min_score=0.0)
        times.append((time.perf_counter() - started) * 1000)
    if not times:
        return {"median": None, "p95": None, "queries": 0}
    return {"median": round(percentile(times, 50), 1), "p95": round(percentile(times, 95), 1), "queries": len(times)}


# ------------------------------------------------------------------------------------- driver

def git_info() -> dict:
    def run(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    return {"commit": run("rev-parse", "--short", "HEAD") or None, "dirty": bool(run("status", "--porcelain"))}


def run(split_name: str, arms: list[str], chunk_size: int, overlap: int, out: Path | None, quiet: bool = False) -> dict:
    pages = load_pages()
    questions = load_questions(*QUESTION_FILES)
    issues = validate(questions, pages)
    if issues:
        raise SystemExit("Dataset is invalid:\n" + "\n".join(f"  {i.question_id}: {i.message}" for i in issues))
    dev, test = split(questions)
    chosen = {"dev": dev, "test": test, "all": sorted(questions, key=lambda q: q.id)}[split_name]
    if not chosen:
        raise SystemExit(f"The {split_name!r} split contains no questions: the dataset is too small to split.")
    norm = normalized_pages(pages)
    chunks = build_chunks(pages, chunk_size, overlap)

    built = {}
    built["tfidf"] = TfidfArm(chunks)
    embedder = None
    if {"embedding", "hybrid"} & set(arms):
        settings = get_settings()
        embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_cache_dir)
        started = time.perf_counter()
        vectors = embed_corpus(chunks, embedder)
        if not quiet:
            print(f"  embeddings ready for {len(chunks)} chunks ({time.perf_counter() - started:.1f}s, cached after the first run)")
        built["embedding"] = EmbeddingArm(chunks, vectors, embedder)
    if "hybrid" in arms:
        built["hybrid"] = HybridArm(built["tfidf"], built["embedding"])

    thr = provisional_thresholds()
    report = {
        "schema": 1, "date": datetime.date.today().isoformat(), "split": split_name,
        "dataset_version": "1", "corpus_version": load_manifest()["corpus_version"],
        "git": git_info(),
        "config": {"chunk_size": chunk_size, "overlap": overlap, "chunks": len(chunks), "pool": POOL,
                   "embedding_model": get_settings().embedding_model, "provisional_thresholds": thr},
        "questions": {"total": len(chosen), "answerable": sum(q.answerable for q in chosen),
                      "unanswerable": sum(not q.answerable for q in chosen),
                      "by_author": {a: sum(q.author == a for q in chosen) for a in sorted({q.author for q in chosen})}},
        "product_tfidf_latency_ms": product_tfidf_latency(chunks, chosen),
        "arms": {},
    }
    for name in arms:
        arm_thr = {"tfidf": thr["tfidf"], "embedding": thr["embedding"]} if name == "hybrid" else {name: thr[name]}
        records = [evaluate_question(built[name], q, norm) for q in chosen]
        report["arms"][name] = report_arm(name, records, arm_thr)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def fmt(s: dict) -> str:
    if s["value"] is None:
        return "   n/a"
    return f"{s['value']:.2f} [{s['ci'][0]:.2f}-{s['ci'][1]:.2f}]"


def print_summary(report: dict) -> None:
    q = report["questions"]
    print(f"\nsplit={report['split']}  questions={q['total']} ({q['answerable']} answerable, {q['unanswerable']} unanswerable)  "
          f"chunks={report['config']['chunks']}  size={report['config']['chunk_size']}/{report['config']['overlap']}")
    print("Values are means with 95% bootstrap intervals. Overlapping intervals = no demonstrated difference.\n")
    header = f"{'method':10} {'Recall@1':18} {'Recall@3':18} {'Recall@5':18} {'MRR':18} {'p50 ms':>7}"
    print(header); print("-" * len(header))
    for name, a in report["arms"].items():
        r = a["ranking"]
        print(f"{name:10} {fmt(r['recall@1']):18} {fmt(r['recall@3']):18} {fmt(r['recall@5']):18} {fmt(r['mrr']):18} {a['latency_ms']['median']:7.1f}")
    print("\nAt the current (provisional) thresholds:")
    for name, a in report["arms"].items():
        o = a["operating_point_at_current_defaults"]
        print(f"  {name:10} correct abstention {fmt(o['abstention_accuracy_on_unanswerable'])}   "
              f"false abstention {fmt(o['false_abstain_rate_on_answerable'])}   end-to-end Recall@3 {fmt(o['end_to_end_recall@3'])}")
    print("\nRecall@3 by question type:")
    types = sorted({t for a in report["arms"].values() for t in a["ranking_by_type"]})
    for t in types:
        cells = "   ".join(f"{n}: {fmt(a['ranking_by_type'][t]['recall@3'])} (n={a['ranking_by_type'][t]['n']})" for n, a in report["arms"].items())
        print(f"  {t:12} {cells}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", default="tfidf,embedding,hybrid")
    parser.add_argument("--chunk-size", type=int, default=950)
    parser.add_argument("--overlap", type=int, default=170)
    parser.add_argument("--final", action="store_true", help="score the held-out TEST split (run once, after all choices are frozen)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    split_name = "test" if args.final else "dev"
    if args.final:
        print("FINAL RUN: scoring the held-out test split. Do not change retrieval code or thresholds based on this output.")
    out = args.out or (DATA_DIR / ".cache" / f"last-{split_name}.json")
    report = run(split_name, args.arms.split(","), args.chunk_size, args.overlap, out)
    print_summary(report)
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
