# Experiments log

Only things actually run are recorded here. These are single hand-made examples to understand behavior, **not benchmarks**. Measured Recall@k / MRR come in M7 on a labeled dataset.

## M3: TF-IDF baseline, first look (2026-11-03)

Setup: one synthetic 3-page document (written by me for this check), chunked with the defaults (each page fit in one chunk, so chunk = page), `min_score=0` to show raw scores, top 3. Vectorizer: English stop words, unigrams + bigrams, sublinear tf.

| Question | Result (page : score) |
|---|---|
| How does the platform decide the next question difficulty? | p1 : 0.235, p2 : 0.0929, p3 : 0.0 |
| What are the limitations of the study? | p3 : 0.4201, p1 : 0.0, p2 : 0.0 |
| Which inputs does the model use? | all pages 0.0 |
| galaxies and nebulae | all pages 0.0 |

### What this shows
1. **Works when the question shares words with the answer.** "limitations" appears in page 3, which ranks first by a wide margin.
2. **Wrong ranking despite overlap (question 1).** The passage that actually answers it is page 2 ("a Random Forest classifier ... selects ... practice for the next question"). Page 1 ranks higher because it repeats the question's words ("difficulty", "question") without explaining the decision. Lexical overlap is not the same as answering.
3. **Vocabulary mismatch (question 3).** The answer is on page 1 ("correctness, execution time and the number of attempts") but the question says "inputs"/"model", which never appear. Every score is 0.0, so the system abstains even though the information exists. This is the main reason to add embedding retrieval (M6/M7) and measure the difference.
4. **Out-of-scope questions score 0.0 here, which is why abstention works.** This is a tiny corpus; with larger documents, a common word can produce small non-zero scores for unrelated questions.

### Score limitations
- Scores are cosine similarity of TF-IDF vectors: relative lexical overlap, not a probability that the answer is present.
- IDF is fit on the chunks being searched, so the same chunk's score can change when the searched set changes (e.g. filtering by document, or uploading more files).
- `MIN_RELEVANCE_SCORE=0.05` is an initial guess. It has not been tuned on labeled questions and must not be presented as validated.

### Next
Build the labeled evaluation set (M7) and re-check items 2 and 3 with measured numbers.
