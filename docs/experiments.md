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

## M6d pre-decision experiment: local embeddings on the same toy document (2026-11-03)

Run before choosing a provider. Same synthetic 3-page text and the same four questions as the TF-IDF experiment above. Model: `BAAI/bge-small-en-v1.5` (384 dimensions, ONNX via `fastembed`, run locally on an Apple M2), with the model's recommended query instruction. Cosine similarity. **One toy document and four questions: an illustration, not a benchmark, and nothing was tuned.**

| Question (correct page) | TF-IDF (from above) | Embeddings (page : cosine) | Top hit correct? |
|---|---|---|---|
| How does the platform decide the next question difficulty? (p2) | p1 0.235, p2 0.093 | p1 0.692, **p2 0.687**, p3 0.498 | No, but a near tie (gap 0.005) |
| What are the limitations of the study? (p3) | p3 0.420 | **p3 0.807**, p1 0.564, p2 0.516 | Yes |
| Which inputs does the model use? (p1) | nothing (0.0 everywhere) | p2 0.613, **p1 0.592**, p3 0.464 | No, but p1 is now ranked 2nd instead of invisible |
| galaxies and nebulae (nothing relevant) | nothing (correct abstention) | p2 0.477, p3 0.470, p1 0.448 | n/a |

### What this shows
1. **Vocabulary mismatch is partly fixed.** "inputs/model" now reaches the right page (rank 2), where TF-IDF returned nothing. With top-k > 1 the evidence is at least retrieved.
2. **Embeddings did not fix the ranking error on question 1.** Both pages are about the same topic, and the model cannot tell "mentions the topic" from "answers the question" (0.692 vs 0.687).
3. **Embeddings never return zero, so abstention gets harder.** An irrelevant question still scores 0.45-0.48, close to a relevant page's 0.59. A relevance threshold (and probably a lexical sanity check) must be tuned on labeled questions (M7); a naive "return the top k" would never say "not enough evidence".
4. **Cost and size:** model files about 64 MB on disk (the library uses a quantized ONNX build; an earlier version of this note said 200 MB because the measuring script double-counted symlinked files); first load about 6 s; about 39 chunks/s on this machine (a 400-chunk PDF in about 10 s); one query embedding about 2 ms; no network call and no document text leaves the machine.
