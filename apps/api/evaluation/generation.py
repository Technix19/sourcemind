"""Do generated answers stay grounded? (M8; the plan is docs/m8-generation-eval.md, written before this ran.)

Runs the product's real answer path (same prompt, same context budget, same citation checks) over the labeled
questions and classifies each result mechanically. It spends real money, so it refuses to run without
--confirm-spend. Nothing here tunes anything: if the prompt or model changes after results are seen, the
held-out claim is gone (see the plan).

    python -m evaluation.generation --runs 3 --confirm-spend
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

from app.answering import SYSTEM_PROMPT, build_user_prompt, check_citations, is_abstention, select_for_context
from app.config import get_settings
from app.llm import GenerationRefused, get_llm_client
from app.retrieval import Hit, SearchChunk

from .arms import POOL, TfidfArm
from .corpus import DATA_DIR, QUESTION_FILES, build_chunks, load_manifest, load_pages
from .dataset import Question, load_questions, normalized_pages, relevant_pages
from .metrics import percentile, summarize

TOP_K = 4            # the product's default
SUPPORT_BAR = 0.80   # pre-registered concern line for the supported-citation rate
OUTCOMES = ("no_evidence", "abstained", "withheld", "answered", "error")


def hits_for(arm, question: str, filenames: dict[str, str], min_score: float, top_k: int = TOP_K) -> list[Hit]:
    """Keyword retrieval exactly as the product applies it: best first, only chunks at or above the threshold."""
    ranked = [r for r in arm.search(question, POOL).ranked if r.score >= min_score][:top_k]
    return [
        Hit(SearchChunk(f"{r.chunk.doc_id}-p{r.chunk.page}-c{r.chunk.index}", r.chunk.doc_id,
                        filenames.get(r.chunk.doc_id, r.chunk.doc_id), r.chunk.page, r.chunk.text), round(r.score, 4))
        for r in ranked
    ]


def run_question(q: Question, hits: list[Hit], client, max_context_chars: int, relevant: set[tuple[str, int]]) -> dict:
    """What the API does after retrieval, classified. Never raises: a failed call is an `error` outcome."""
    record: dict = {"id": q.id, "type": q.type, "answerable": q.answerable, "question": q.question}
    if not hits:
        return record | {"outcome": "no_evidence", "evidence": [], "evidence_has_answer": False}
    sent = select_for_context(hits, max_context_chars)
    pages = [(h.chunk.document_id, h.chunk.page_number) for h in sent]
    record |= {"evidence": [list(p) for p in pages], "evidence_has_answer": any(p in relevant for p in pages)}
    started = time.perf_counter()
    try:
        raw = client.complete(SYSTEM_PROMPT, build_user_prompt(q.question, sent))
    except GenerationRefused:
        return record | {"outcome": "error", "reason": "refusal"}
    except Exception as exc:  # never log messages: they can carry request details
        return record | {"outcome": "error", "reason": type(exc).__name__}
    record["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    usage = getattr(client, "last_usage", None)
    if usage:
        record["usage"] = usage
    if is_abstention(raw):
        return record | {"outcome": "abstained", "answer": raw.strip()}
    checked = check_citations(raw, len(sent))
    if not checked.cited:
        return record | {"outcome": "withheld", "answer": checked.text, "invalid_citations": checked.removed}
    return record | {
        "outcome": "answered", "answer": checked.text, "cited": checked.cited, "invalid_citations": checked.removed,
        "supported": any(pages[n - 1] in relevant for n in checked.cited),
    }


def aggregate(records: list[dict]) -> dict:
    """The pre-registered metrics (docs/m8-generation-eval.md), each with a 95% bootstrap interval."""
    answerable = [r for r in records if r["answerable"]]
    with_evidence = [r for r in answerable if r["evidence_has_answer"]]
    without = [r for r in answerable if not r["evidence_has_answer"]]
    unanswerable = [r for r in records if not r["answerable"]]
    flag = lambda rows, test: [1.0 if test(r) else 0.0 for r in rows]  # noqa: E731
    answered = [r for r in with_evidence if r["outcome"] == "answered"]
    latencies = [r["latency_ms"] for r in records if "latency_ms" in r]
    tokens = {k: sum(r.get("usage", {}).get(k, 0) for r in records) for k in ("input_tokens", "output_tokens")}
    supported = summarize(flag(answered, lambda r: r["supported"]))
    return {
        "outcomes": {o: sum(1 for r in records if r["outcome"] == o) for o in OUTCOMES},
        "answerable_with_evidence": {
            "answer_rate": summarize(flag(with_evidence, lambda r: r["outcome"] == "answered")),
            "supported_citation_rate": supported,
            "wrong_abstention_rate": summarize(flag(with_evidence, lambda r: r["outcome"] == "abstained")),
        },
        "answerable_without_evidence": {
            "answered_anyway": summarize(flag(without, lambda r: r["outcome"] == "answered")),
        },
        "unanswerable": {
            "invented_answer_rate": summarize(flag(unanswerable, lambda r: r["outcome"] == "answered")),
            "product_abstained": summarize(flag(unanswerable, lambda r: r["outcome"] in ("no_evidence", "abstained"))),
            "model_was_called": sum(1 for r in unanswerable if r["outcome"] != "no_evidence"),
        },
        "latency_ms": {"median": percentile(latencies, 50), "p95": percentile(latencies, 95), "calls": len(latencies)},
        "tokens": tokens,
        "concerns": concerns(records, supported),
    }


def concerns(records: list[dict], supported: dict) -> list[str]:
    """The judgment lines fixed in advance. Reported, never hidden."""
    found = [f"Answered an unanswerable question: {r['id']}" for r in records if not r["answerable"] and r["outcome"] == "answered"]
    if supported["value"] is not None and supported["value"] < SUPPORT_BAR:
        found.append(f"Supported-citation rate {supported['value']:.2f} is below the {SUPPORT_BAR:.2f} line")
    found += [f"Model call failed on {r['id']} ({r.get('reason')})" for r in records if r["outcome"] == "error"]
    return found


def unstable(runs: list[list[dict]]) -> list[dict]:
    """Questions whose outcome differs between runs (a pre-registered concern)."""
    out = []
    for per_question in zip(*runs):
        outcomes = [r["outcome"] for r in per_question]
        if len(set(outcomes)) > 1:
            out.append({"id": per_question[0]["id"], "outcomes": outcomes})
    return out


def _git() -> dict:
    run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, cwd=DATA_DIR).stdout.strip()  # noqa: E731
    return {"commit": run("rev-parse", "--short", "HEAD"), "dirty": bool(run("status", "--porcelain", "--", "."))}


def evaluate(client, *, runs: int = 3, limit: int | None = None) -> dict:
    settings = get_settings()
    pages = load_pages()
    chunks = build_chunks(pages, settings.chunk_size, settings.chunk_overlap)
    arm, norm = TfidfArm(chunks), normalized_pages(pages)
    filenames = {d["id"]: d["file"] for d in load_manifest()["documents"]}
    questions = load_questions(*QUESTION_FILES)[:limit]
    per_run: list[list[dict]] = []
    for _ in range(runs):
        records = []
        for q in questions:
            hits = hits_for(arm, q.question, filenames, settings.min_relevance_score)
            records.append(run_question(q, hits, client, settings.max_context_chars, relevant_pages(q, norm) if q.answerable else set()))
        per_run.append(records)
    return {
        "run": {
            "date": datetime.date.today().isoformat(), "git": _git(), "model": client.model, "effort": settings.answer_effort,
            "max_tokens": settings.max_answer_tokens, "top_k": TOP_K, "min_relevance_score": settings.min_relevance_score,
            "max_context_chars": settings.max_context_chars, "questions": len(questions), "runs": runs,
        },
        "runs": [{"records": records, "metrics": aggregate(records)} for records in per_run],
        "unstable_questions": unstable(per_run),
    }


def build_report(results: dict) -> str:
    run = results["run"]
    fmt = lambda s: "n/a" if s["value"] is None else f"{s['value']:.2f} ({s['ci'][0]:.2f} to {s['ci'][1]:.2f}), n={s['n']}"  # noqa: E731
    lines = [
        "# Generated-answer evaluation", "",
        f"Run on {run['date']} at commit `{run['git']['commit']}`{' (working tree had uncommitted changes)' if run['git']['dirty'] else ''}. "
        f"Model `{run['model']}`, effort `{run['effort']}`, {run['questions']} questions x {run['runs']} runs, keyword retrieval "
        f"(top {run['top_k']}, minimum score {run['min_relevance_score']}). Plan: `docs/m8-generation-eval.md`, written before the run.", "",
        "Values are means with 95% bootstrap intervals over questions. **This checks that cited pages contain the labeled answer, "
        "not that the answer text is true.** Small sample, one author, one model.", "",
        "| Metric | " + " | ".join(f"Run {i}" for i in range(1, run["runs"] + 1)) + " |",
        "|---|" + "---|" * run["runs"],
    ]
    rows = [
        ("Answer rate (evidence available)", lambda m: fmt(m["answerable_with_evidence"]["answer_rate"])),
        ("Supported-citation rate (of answered)", lambda m: fmt(m["answerable_with_evidence"]["supported_citation_rate"])),
        ("Wrong abstention (evidence available)", lambda m: fmt(m["answerable_with_evidence"]["wrong_abstention_rate"])),
        ("Answered although no relevant page was retrieved", lambda m: fmt(m["answerable_without_evidence"]["answered_anyway"])),
        ("Invented answer on an unanswerable question", lambda m: fmt(m["unanswerable"]["invented_answer_rate"])),
        ("Product abstained on unanswerable", lambda m: fmt(m["unanswerable"]["product_abstained"])),
    ]
    for label, get in rows:
        lines.append(f"| {label} | " + " | ".join(get(r["metrics"]) for r in results["runs"]) + " |")
    lines += ["", "## Outcomes per run", "", "| Run | " + " | ".join(OUTCOMES) + " |", "|---|" + "---|" * len(OUTCOMES)]
    for i, r in enumerate(results["runs"], start=1):
        lines.append(f"| {i} | " + " | ".join(str(r["metrics"]["outcomes"][o]) for o in OUTCOMES) + " |")
    lines += ["", "## Concerns (pre-registered lines)", ""]
    seen = [c for r in results["runs"] for c in r["metrics"]["concerns"]]
    lines += [f"- {c}" for c in dict.fromkeys(seen)] or ["- None of the pre-registered concern lines was crossed."]
    if results["unstable_questions"]:
        lines += ["", "Questions whose outcome changed between runs: " + ", ".join(
            f"`{u['id']}` ({' / '.join(u['outcomes'])})" for u in results["unstable_questions"]) + "."]
    else:
        lines += ["", "No question changed outcome between runs."]
    t = results["runs"][0]["metrics"]
    total = {k: sum(r["metrics"]["tokens"][k] for r in results["runs"]) for k in ("input_tokens", "output_tokens")}
    lines += ["", f"Latency per call (run 1): median {t['latency_ms']['median']} ms, p95 {t['latency_ms']['p95']} ms. "
              f"Tokens used across all runs: {total['input_tokens']:,} in, {total['output_tokens']:,} out.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions (for a cheap smoke test)")
    parser.add_argument("--confirm-spend", action="store_true", help="required: this makes paid model calls")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "results")
    args = parser.parse_args(argv)
    if not args.confirm_spend:
        print("This makes real, paid model calls. Re-run with --confirm-spend to proceed.")
        return 2
    client = get_llm_client()
    if client is None:
        print("Generation is not configured: set ANTHROPIC_API_KEY and ANTHROPIC_MODEL.")
        return 2
    results = evaluate(client, runs=args.runs, limit=args.limit)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"generation-{results['run']['date']}" + (f"-limit{args.limit}" if args.limit else "")
    (args.out / f"{stem}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    (args.out / f"{stem}.md").write_text(build_report(results))
    print(build_report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
