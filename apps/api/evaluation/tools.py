"""Plain-text helpers for writing evaluation questions. None of them touches a retriever.

    python -m evaluation.tools find "phrase to look for" [--doc nist-csf]   # Ctrl-F over the whole corpus
    python -m evaluation.tools page nist-csf 14                             # read one page exactly as the app sees it
    python -m evaluation.tools validate [--file external_questions.json]    # check a questions file (default: blind_questions.json)
    python -m evaluation.tools assign --file blind_questions.json           # freeze dev/test labels for newly added questions

Using these keeps a question BLIND: you only look at the documents, never at what a search returns.
"""
from __future__ import annotations

import argparse
import re
import sys

from .corpus import DATA_DIR, load_manifest, load_pages, normalize
from .dataset import assign_splits, load_questions, normalized_pages, relevant_pages, validate


def find(pages: dict[str, list[str]], phrase: str, doc: str | None = None, limit: int = 8, width: int = 90) -> list[str]:
    """Where a phrase occurs (case- and line-break-insensitive), with a little context."""
    needle = normalize(phrase)
    if not needle:
        return ["Type a phrase to look for."]
    lines: list[str] = []
    total = 0
    for doc_id, doc_pages in pages.items():
        if doc and doc_id != doc:
            continue
        for number, raw in enumerate(doc_pages, start=1):
            text = normalize(raw)
            start = text.find(needle)
            while start != -1:
                total += 1
                if len(lines) < limit:
                    lines.append(f"{doc_id} p{number}: ...{text[max(0, start - width):start]}[{text[start:start + len(needle)]}]{text[start + len(needle):start + len(needle) + width]}...")
                start = text.find(needle, start + 1)
    if total == 0:
        return [f"No match for {phrase!r}. If the PDF breaks the phrase across lines with a hyphen, or uses special characters, try a shorter phrase."]
    if total > limit:
        lines.append(f"... and {total - limit} more matches")
    return [f"{total} match(es). A page counts as relevant to a question if your answer phrase appears on it."] + lines


def show_page(pages: dict[str, list[str]], doc: str, number: int) -> str:
    if doc not in pages:
        return f"Unknown document {doc!r}. Choose one of: {', '.join(pages)}"
    if not 1 <= number <= len(pages[doc]):
        return f"{doc} has pages 1-{len(pages[doc])}."
    return f"--- {doc} page {number} of {len(pages[doc])} (PDF page number, which is what the app uses) ---\n" + re.sub(r"[ \t]+", " ", pages[doc][number - 1])


def check_file(pages: dict[str, list[str]], path) -> list[str]:
    """Friendly validation of a questions file."""
    if not path.exists():
        return [f"{path.name} does not exist yet."]
    questions = load_questions(path)
    if not questions:
        return [f"{path.name} contains no questions yet."]
    issues = validate(questions, pages)
    norm = normalized_pages(pages)
    lines = []
    bad = {i.question_id for i in issues}
    for q in questions:
        if q.id in bad:
            continue
        kind = f"relevant on {len(relevant_pages(q, norm))} page(s)" if q.answerable else "answer proven absent"
        lines.append(f"OK    {q.id:12} {q.type:22} {kind}")
    for i in issues:
        lines.append(f"FIX   {i.question_id:12} {i.message}")
    lines.append(f"\n{len(questions) - len(bad)} of {len(questions)} questions are valid.")
    return lines


def freeze_splits(path, seed: int = 20261103) -> list[str]:
    """Write a frozen dev/test label into every question of `path` that does not have one yet.

    Existing labels are never changed, so questions can be added later without moving anything.
    """
    import json

    data = json.loads(path.read_text())
    questions = load_questions(path)
    todo = [q for q in questions if not q.split]
    if not todo:
        return ["Every question already has a frozen split."]
    assignment = assign_splits(todo, seed)
    for raw in data["questions"]:
        if raw["id"] in assignment and not raw.get("split"):
            raw["split"] = assignment[raw["id"]]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    counts = {h: sum(v == h for v in assignment.values()) for h in ("dev", "test")}
    return [f"Froze splits for {len(todo)} question(s) in {path.name}: {counts['dev']} dev, {counts['test']} test."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("find"); f.add_argument("phrase"); f.add_argument("--doc")
    p = sub.add_parser("page"); p.add_argument("doc"); p.add_argument("number", type=int)
    v = sub.add_parser("validate"); v.add_argument("--file", default="blind_questions.json", help="a file in data/evaluation/ (e.g. external_questions.json)")
    a = sub.add_parser("assign"); a.add_argument("--file", required=True, help="freeze dev/test labels for the questions in this file (in data/evaluation/)")
    args = parser.parse_args(argv)
    docs = [d["id"] for d in load_manifest()["documents"]]
    pages = load_pages()
    if args.command == "find":
        print("\n".join(find(pages, args.phrase, args.doc)))
    elif args.command == "page":
        print(show_page(pages, args.doc, args.number))
    elif args.command == "assign":
        print("\n".join(freeze_splits(DATA_DIR / args.file)))
        return 0
    else:
        out = check_file(pages, DATA_DIR / args.file)
        print("\n".join(out))
        return 0 if all(not line.startswith("FIX") for line in out) else 1
    print(f"\n(documents: {', '.join(docs)})") if args.command != "validate" else None
    return 0


if __name__ == "__main__":
    sys.exit(main())
