# Writing your blind evaluation questions (about 10, 30-45 minutes)

**Why this matters.** The questions I wrote reuse words from the pages I read, which flatters keyword search. Yours are the credibility check: you write them from *your own* reading, in *your own* words, **without ever seeing what the app returns**.

## The one rule
**Do not run the app (or any search) on a question before you have written it down.** Only read the documents. The helper tools below are plain text search; they never run a retriever, so they are safe to use.

## 1. Read (skim) the documents
They are PDFs in `data/evaluation/corpus/` (open them in Preview):

| id | file | what it is |
|---|---|---|
| `nist-ai-rmf` | `nist-ai-rmf.pdf` | NIST AI Risk Management Framework |
| `nist-csf` | `nist-csf.pdf` | NIST Cybersecurity Framework 2.0 |
| `nhlbi-sleep` | `nhlbi-sleep.pdf` | NIH guide to healthy sleep |
| `fed-explained` | `fed-explained.pdf` | The Federal Reserve, explained |
| `us-constitution` | `us-constitution.pdf` | The US Constitution (with an analytical index) |

Skim a few sections of at least three of them. You don't need to read everything.

## 2. Write about 10 questions in `data/evaluation/blind_questions.json`

Suggested mix (it is fine to deviate a little):

| How many | type | what to write |
|---|---|---|
| 5 | `paraphrase` | A question whose **meaning** matches a passage but whose **words** deliberately differ, the way a real user would phrase it. These matter most. |
| 1 | `direct` | A question that reuses the document's own words. |
| 1 | `specific` | A question about one concrete fact (a number, a name, a list). |
| 2 | `unanswerable_related` | A question about a document's topic whose answer is **not** in the document. |
| 1 | `unanswerable_offtopic` | A question unrelated to all of the documents. |

Each entry looks like this (put them inside the `"questions": [ ... ]` list, separated by commas):

```json
{
  "id": "owner-01",
  "type": "paraphrase",
  "author": "owner",
  "question": "Why do people feel groggy after only a little sleep?",
  "doc": "nhlbi-sleep",
  "answer": "short note for yourself, e.g. 'one night of too little sleep hurts mood and functioning'",
  "answer_spans": ["Just one night of inadequate sleep can negatively affect your functioning"]
}
```

* `id`: `owner-01`, `owner-02`, ... (must be unique).
* `author`: always `"owner"`.
* `doc`: the document id from the table above.
* `answer_spans`: **one or more exact phrases from the document that answer the question.** Any page containing a phrase counts as a correct page. Use the finder below to copy exact text. Pick a distinctive phrase of 4-10 words; avoid ones that cross a hyphenated line break.
* **Unanswerable questions** have no `answer_spans`. Instead list `absent_terms`: words that would appear if the document *did* answer it, which you have checked are **not** in that document. Example:

```json
{
  "id": "owner-09",
  "type": "unanswerable_related",
  "author": "owner",
  "question": "How much does a sleep study cost?",
  "doc": "nhlbi-sleep",
  "absent_terms": ["cost of a sleep study", "re:\\$\\d"]
}
```
  (A term starting with `re:` is a regular expression. If `absent_terms` is hard, just list one or two plain words you checked with `find`.)

## 3. Helper tools (run from `apps/api` with the venv active)

```bash
python -m evaluation.tools find "inadequate sleep"           # Ctrl-F across all documents, with context
python -m evaluation.tools find "inadequate sleep" --doc nhlbi-sleep
python -m evaluation.tools page nhlbi-sleep 27               # read one page as the app sees it
python -m evaluation.tools validate                           # check your file; tells you exactly what to fix
```

`validate` fixes mistakes in *your labels* (a phrase that does not exist, a typo in a document id). It shows nothing about how well any search works.

## 4. When you are done
Run `validate` until every question says `OK`, then tell me. **Please do not run the app on these questions first**, and do not edit a question after you have seen how a search handled it.
