# M7 design: measured evaluation, then release hardening

Status: **7a implemented (corpus, 45 questions, harness, tools); 7b-7d not started.** Decisions made with the owner: use the five documents; deployment planned from the start (with explicit confirmation before anything is created or made public). The owner chose to have the assistant write the extra ten questions instead of writing blind questions, so the dataset currently has **a single author** (see "Authorship" below). M7 is the milestone that replaces "it seems to work" and my provisional thresholds with measured, reproducible evidence, and states honestly where retrieval fails.

## Sub-steps
| Step | Delivers |
|---|---|
| **7a** Corpus, labeled questions, evaluation harness | Reproducible `Recall@k`, `MRR`, abstention accuracy, latency for keyword vs meaning search |
| **7b** Analysis, tuned thresholds, results page | Failure analysis, chunking experiments, measured defaults replacing the guesses, an Evaluation page showing only real results |
| **7c** Release hardening | The pre-launch checklist (rate and cost caps, Content-Security-Policy, email confirmation, stale-row cleanup, docs lockdown) |
| **7d** Deployment (optional, owner decides after 7b) | Hosted demo with published limits |

## The corpus (public domain, fetched not committed)
Five real US federal publications, chosen for variety of subject and style. All fetched successfully and extract cleanly with our own pipeline.

| Document | Kind | Pages | Chunks (default size) |
|---|---|---|---|
| NIST AI Risk Management Framework 1.0 | technical policy | 48 | 170 |
| NIST Cybersecurity Framework 2.0 | technical standard | 32 | 102 |
| NHLBI "Your Guide to Healthy Sleep" | plain-language health | 72 | 168 |
| Federal Reserve "The Fed Explained" | economics / institutions | 135 | 472 |
| "The Constitution of the United States of America" (House Doc. 110-50) | legal / historical | 85 | 433 |

About 372 pages and 1,345 chunks in total. A `fetch_corpus` script downloads each file and **verifies its SHA-256**, so a changed source fails loudly instead of silently shifting the results; PDFs are not committed (keeps the repo small, avoids redistributing). `SOURCES.md` records each URL, retrieval date, hash and licensing basis (US federal government work, 17 U.S.C. 105; no restrictive notice found in the text; not legal advice). Real PDFs matter: they bring headers, hyphenation and tables, which is what real retrieval faces.

## The labeled questions (about 44, stratified)
| Type | Count | Purpose |
|---|---|---|
| `direct` (reuses the document's own wording) | ~12 | the easy case, where keyword search should do well |
| `paraphrase` (same meaning, deliberately different words) | ~12 | the case meaning search is supposed to help |
| `specific` (a fact or number on one page among many similar pages) | ~8 | ranking precision |
| `unanswerable_related` (on topic, but the corpus does not say) | ~6 | abstention that is hard |
| `unanswerable_offtopic` (nothing to do with the corpus) | ~6 | abstention that is easy |

Each answerable question records: the document, the relevant page(s), and an `answer_span` (a short exact phrase from that page). A dataset-validity test fails if any span is missing from its page's extracted text, so labels cannot rot silently. **Relevance is page-level** (document + page), so the result does not depend on chunk boundaries and survives chunking experiments.

**Honest caveat about authorship.** Whoever writes the questions after reading the pages tends to reuse the pages' words, which flatters keyword search. Mitigations: the `paraphrase` type is constructed on purpose and reported separately, and questions written *blind* (without looking at any retriever output) are tagged and reported separately.

## Authorship: what this evaluation can and cannot show
All 45 questions were written by the assistant: batch 1 (35) from reading pages only; batch 2 (10, ids `x-01`..`x-10`) added later, **after the development results of batch 1 had been seen**, as a substitute for the owner's blind questions (also written from page text only and not run on any search first). There is therefore **no independent-author check**: wording bias toward keyword search cannot be ruled out, and batch 2 was shaped by what I had already learned. The report must say so. The pipeline still supports independent questions (`blind_questions.json` for the owner, `external_questions.json` for another AI, each tagged and reported separately); adding them later improves the evidence without changing any code.

## The split is frozen in the data file
Every question carries a `split` label (`dev` or `test`). While adding batch 2 I found that the original scheme, a shuffle inside each group, would have moved three questions whose development results I had already examined into the test half, because a shuffle depends on who else is in the group. Labels are now explicit and frozen: batch 1 keeps exactly the assignment I had seen; later questions are labeled once with `python -m evaluation.tools assign --file <file>` and never move. A regression test pins batch 1's assignment.

## Metrics, and how not to fool ourselves
- **Recall@k** (k = 1, 3, 5): fraction of answerable questions with a relevant page in the top k. **MRR**: mean reciprocal rank of the first relevant page. **Precision@k** reported but secondary.
- **Abstention accuracy** on unanswerable questions (returns no evidence) and the **false-abstain rate** on answerable ones. They trade off, so both are always shown, with the full threshold sweep.
- **Latency**: median and p95 retrieval time per method. (Citation accuracy needs a language-model key and is **not measured**; the report says so.)
- **Dev / test split** (fixed seed, stratified by type): thresholds are tuned on dev only; every headline number is on test. With about 20 test questions the intervals are wide, so every number carries a **bootstrap 95% confidence interval**, and a difference between methods that sits inside the intervals is reported as *not demonstrated*.
- **Three arms:** keyword, meaning, and an experimental *hybrid* (reciprocal-rank fusion) that exists only in the harness. It joins the product only if the numbers justify it and the owner agrees.
- **Experiments:** chunk size (500 / 950 / 1500) and `top_k`, reported as measured, not as advice.

## Pre-registered analysis plan (written 2026-11-04, BEFORE any tuning and BEFORE the test split was scored)

These rules were fixed in advance so the results cannot be steered by what the numbers turn out to be.

1. **Thresholds.** Tuned per method on the **dev** split only. Objective: **balanced accuracy** = the mean of (correct-abstention rate on unanswerable questions) and (1 - false-abstention rate on answerable questions), i.e. wrongly answering and wrongly refusing are weighted equally. Grid: keyword 0.00-0.40 and meaning 0.40-0.90, both in steps of 0.01. If several values tie, the **median** of the tied values is used (the middle of a plateau, not its edge). The hybrid method is not tuned separately: it uses the two tuned thresholds and answers if either clears its own.
2. **Chunk size.** Candidates 500, 950 (current) and 1500 characters, overlap about 18%. Evaluated on dev only. **950 is kept unless another size beats it on both Recall@3 and MRR by at least 0.10.** Thresholds are tuned after the chunk size is fixed.
3. **Default search method in the product** stays *keyword*. It would only be **recommended** for change if, on the **test** split, meaning (or hybrid) has higher point estimates for both Recall@3 and MRR, and its balanced accuracy at the tuned threshold is not lower. Because the intervals will overlap at this sample size, a change would be a recommendation for the owner to decide, never an automatic switch.
4. **Reporting.** The test split is scored **once**, after thresholds and chunk size are frozen. Every number carries a 95% bootstrap interval; two methods are described as different only when their intervals do not overlap. Dev results are shown separately and labeled as dev.
5. **After the test run**: no change to retrieval code, thresholds, labels or questions. The failure analysis is descriptive only.

## The harness
A separate `evaluation` package (not part of the API) runs the exact same chunker, the same TF-IDF code and the same embedder against the corpus in memory, so it needs no accounts or database and anyone can reproduce it with one command. To make sure it measures what ships, an opt-in **parity test** uploads part of the corpus to the real project and checks that the production API returns the same top results as the harness. Output: a versioned JSON (dataset version, date, git commit, config, metrics, intervals, per-question results) plus a Markdown report; the Evaluation page renders the JSON and nothing else.

## 7b: what the numbers will be allowed to change
- `MIN_RELEVANCE_SCORE` and `MIN_EMBEDDING_SCORE` get measured defaults from the dev split, documented as "tuned on five public documents; may not transfer".
- The default retrieval method changes only if test results clearly favor it.
- A failure analysis lists the worst misses with the question, the expected page and what was returned, and explains each. That page is probably the most valuable thing in the portfolio.

## 7c: release hardening checklist
Per-user rate limits and a daily cap on generated answers; a Content-Security-Policy header (web and API); email confirmation back on, and a real SMTP sender (Supabase's built-in one is limited to a few emails an hour); a sweep for stale `indexing` documents; API docs and OpenAPI disabled outside local; document and data-retention statement; a "what this is and is not" README section.

## 7d: deployment (only if you want it)
Outward-facing and possibly costly (a Python host with enough memory for the local model, a web host, a domain), so it is a separate decision after 7b, with explicit confirmation before anything is created.
