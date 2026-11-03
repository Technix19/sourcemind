# Retrieval evaluation

Measures how well the product's two search methods (keyword / TF-IDF and meaning / embeddings) find the right page, using real public-domain PDFs and labeled questions. Design and caveats: `docs/m7-design.md`.

## Reproduce

```bash
python data/evaluation/fetch_corpus.py        # downloads 5 PDFs and verifies their SHA-256 (not committed)
cd apps/api && source .venv/bin/activate
python -m evaluation.run                      # DEVELOPMENT split: safe to look at while building
python -m evaluation.run --final              # held-out TEST split: run once, after every choice is frozen
```

The first run embeds about 1,345 chunks with the local model (about 80 s) and caches the vectors; later runs take seconds.

## What is here

| File | Purpose |
|---|---|
| `corpus.manifest.json` | the five documents: URL, SHA-256, publisher, licensing basis |
| `fetch_corpus.py` | download and verify (a changed source is an error, never silently accepted) |
| `questions.json` | questions written by the assistant, from reading the pages only |
| `blind_questions.json` | questions written by the project owner, blind (`BLIND_QUESTIONS.md`) |
| `results/` | committed final results (7b) |
| `.cache/` | embeddings and development runs (git-ignored, derived data) |

## How labels work (important)

An answerable question lists literal `answer_spans`. **A page is relevant if any span appears on it**, so labels are mechanical: no hand-picked page numbers to drift, and facts repeated across pages (such as the Constitution's index) are treated consistently. Unanswerable questions list `absent_terms`, which must not appear in the topical document (checked by the validator). Run `python -m evaluation.tools validate` after editing a questions file.

## The dev/test split is frozen

Each question has a `split` label (`dev` or `test`) written in the data file; it never changes. To add questions, put them in `blind_questions.json` or `external_questions.json` (ids and format: `BLIND_QUESTIONS.md`, `EXTERNAL_QUESTIONS_PROMPT.md`), run `python -m evaluation.tools validate --file <file>`, then `python -m evaluation.tools assign --file <file>` once to freeze their labels. Never relabel a question after its results have been looked at.

## Authorship

Questions are tagged `assistant`, `owner` or `external_llm` and reported separately. Currently **all 45 are `assistant`** (35 plus a later batch of 10), so there is no independent-author check yet.

## Rules that keep the numbers honest

1. Questions are written **before** any retriever sees them, and are not edited after a search handled them.
2. Thresholds and design choices are tuned on the **dev** split only. The **test** split is scored once, with `--final`.
3. Every number carries a 95% bootstrap interval. If the intervals of two methods overlap, the difference is **not demonstrated**.
4. Not measured here: citation accuracy of generated answers (needs a language-model key) and production latency (network and database time).
