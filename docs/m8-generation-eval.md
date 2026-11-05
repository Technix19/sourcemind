# M8: Do generated answers stay grounded? (pre-registered plan)

Written 2026-11-05, **before** the harness was built and before any model call was made for it.

M7 measured retrieval only. This measures the other half of the product's promise: when Claude writes an answer from the
retrieved passages, is it grounded in them, and does it say "not enough evidence" when it should?

## What is run

The product's real answer path, on the existing 45 labeled questions (26 dev, 19 test, five public-domain US documents):

- Retrieval: keyword (TF-IDF), minimum score 0.05, top 4, 8,000-character context budget. These are the hosted demo's settings.
- The product's own `SYSTEM_PROMPT`, `build_user_prompt`, `select_for_context`, `check_citations` and `is_abstention`
  (a parity test proves the harness builds the same prompt the API does).
- The real model client: `claude-haiku-5-5`, effort `low`, `max_tokens` 2000. No temperature (current models reject it).
- **Three runs** over all questions, because the model's output is not deterministic. Each run is reported; no averaging
  hides disagreement.

**No tuning.** The prompt, model and settings are fixed before the run. All 45 questions are used and nothing is held out,
because nothing is being tuned. **If I change the prompt, model or settings after seeing results, this run becomes
development evidence, the held-out claim is gone, and any new run must say so.**

## Outcomes (defined mechanically, now)

For each question the product ends in exactly one outcome:

| Outcome | Meaning |
|---|---|
| `no_evidence` | retrieval found nothing above the threshold, so no model call is made (the product abstains) |
| `abstained` | the model replied with the exact abstention sentence |
| `withheld` | the model answered but with no citation that resolves to the evidence, so the product hides the answer |
| `answered` | the model answered with at least one valid citation |
| `error` | the model call failed (counted separately, never as success) |

Relevance reuses M7's labels: a page is **relevant** if a labeled answer phrase appears on it. A cited passage is
**supported** if its (document, page) is relevant. This is page-level, not sentence-level.

## Metrics

On **answerable** questions where a relevant page was among the passages sent to the model ("evidence available"):
1. **Answer rate**: share ending `answered`.
2. **Supported-citation rate**: of `answered`, the share where at least one cited passage is on a relevant page.
3. **Wrong abstention rate**: share ending `abstained` despite evidence being available.

On answerable questions where **no relevant page was retrieved**:
4. **Answered without the evidence**: share ending `answered` anyway (the model had nothing to base the answer on).

On **unanswerable** questions:
5. **Invented answer rate**: share where a model call was made and it ended `answered`. Each one is read by hand.
6. **Product abstained** (`no_evidence` or `abstained`): the complement.

Everything carries a 95% bootstrap interval over questions, and the three runs are shown side by side.

## What would count as a concern (judgment lines, not tests)

Set now so they cannot drift: any `answered` outcome on an unanswerable question; a supported-citation rate below 0.80; or
a question whose outcome category changes between runs. A concern is reported and discussed, not hidden. With
so few questions an interval will be wide, and **a clean result would still not prove the answers are correct.**

## What this cannot show (stated up front)

- **It does not grade whether the answer text is true.** A supported citation means the cited page contains the labeled
  phrase, not that the sentence the model wrote is right. I will read the produced answers and note failures, but that
  reading is by the same assistant that wrote the questions, unblinded, and is labeled as such.
- One model, one effort level, one prompt, five documents, 45 questions written by one author.
- Keyword retrieval only (the hosted configuration). Meaning-search retrieval is not exercised here.
- Documents in the corpus are benign. **Prompt-injection resistance is not measured**; the code treats document text as
  untrusted data and has tests with a fake model, but no real-model injection test exists yet.
- Cost: roughly 135 model calls (45 questions x 3 runs) on a small model. Expected to be a few cents; the real
  token usage is recorded in the results.

---

# Results (run 2026-11-05, commit `47e9d10`, 3 runs of 45 questions)

Full tables: `data/evaluation/results/generation-2026-11-05.md` and `.json` (every answer is stored). Actual usage was 168,810
input and 35,367 output tokens (about 4 cents at the rates assumed in the plan), no call failed.

## 1. As pre-registered (strict rules, unchanged)

| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Answerable, evidence available (n=22): answered | 22 | 22 | 22 |
| ...of which a cited passage is on a relevant page | 22 | 22 | 22 |
| ...wrongly abstained | 0 | 0 | 0 |
| Answerable, no relevant page retrieved (n=11): answered anyway | 9 | 9 | 7 |
| Unanswerable (n=12): `answered` (strict rule) | 8 | 7 | 7 |

Two pre-registered concern lines were **crossed**: unanswerable questions ended `answered`, and 8 questions changed outcome
between runs. Read as written, the strict result looks bad (a 58 to 67% "invented answer rate"). **It is not what it seems; see 2 and 3.**

## 2. Read by hand (the plan required this for every flagged answer)

All 22 `answered` outcomes on unanswerable questions, across the three runs, **begin with the exact abstention sentence**
("I couldn't find that information in the uploaded documents.") and then describe what the retrieved passages do cover, with
citations. I read the first 330 characters of the replies to the ten flagged questions in all three runs (30 replies): none
states the missing fact (no melatonin dose, no cryptocurrency, no Marbury v. Madison holding, no World Cup winner). I did not
read every reply in full, so this is a strong sample, not a proof. This reading is by the assistant that wrote the questions, unblinded.

The product only counts a reply as an abstention when the **whole** reply is that one sentence (`is_abstention` in
`app/answering.py`), so these replies were classified `answered`. The prompt says "reply exactly", and the model (Haiku 5.5, low
effort) often adds an explanation anyway.

## 3. Post-hoc re-scoring (NOT pre-registered; deterministic, on the stored answers, no new model calls)

Treating "starts with the abstention sentence" as an abstention:
- Unanswerable questions: **12 of 12 abstained in every run**; 0 still answered.
- Answerable questions with evidence: 0 of 22 start with the abstention sentence, so the rule would not hurt real answers.
- Questions whose category still changes between runs: 1 (`rmf-04`, a hedged answer to an ethics question), down from 8.

Most of the "instability" was the same behavior with different wording or citation formatting.

## 4. The answerable questions where retrieval missed the labeled page (9 of 11 answered)

Several of these are **correct answers taken from other pages**: `fed-02` (maximum employment and price stability),
`con-02` (the First Amendment) and `x-08` (poll tax) are right, because the same fact appears on pages the page-level labels
do not count. That is the label incompleteness already documented for `con-04`, not hallucination. `csf-03`, `rmf-04` and
`x-02` are hedged partial answers; I did not judge their quality further. So "answered although no relevant page was
retrieved" is **not** a hallucination rate.

## 5. What this means

**A product flaw, found by reading the answers.** Because `is_abstention` is an exact match, an abstention followed by an
explanation is shown as a normal generated answer: the response has `insufficient_evidence: false`, and the UI shows the
green **"Grounded"** badge (`badgeFor` in `TurnView.tsx`) on a reply that begins "I couldn't find that information".
The text is honest; the badge contradicts it. Likely fixes (the owner's call): treat a reply that starts with the sentence as an
abstention (and show "Not enough evidence"), and/or tighten the prompt. **Either change means this run is development
evidence**; confirming a fix needs a new run on questions not used to choose it, and the 45 questions are now all used.

**Not shown by this evaluation:**
- That the answer text is true (supported means the cited page contains the labeled phrase).
- Anything about other models, other effort levels, meaning search or other documents.
- Resistance to prompt injection (no injected documents were used).
- The hedged and partial answers (`csf-03`, `rmf-04`, `x-02`) were not graded.
- Whether users would want the explanation after the abstention sentence (a design question, not a measurement).
