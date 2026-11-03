# M6d design: embeddings and vector search

Status: **implemented: 246 backend + 73 frontend offline tests pass; real-project tests (12) are written and wait for the owner to apply migration 3** (`docs/m6d-apply.md`). Decisions made with the owner: local model, visible Search method control. Builds on `docs/m6-plan.md` (search must be exactly as protected as ordinary reads).

## Evidence gathered first
See the dated experiment at the end of `docs/experiments.md`. Short version: a small local model recovers some vocabulary-mismatch misses, does **not** fix "mentions the topic vs answers the question", and **never scores zero**, so "not enough evidence" now needs a tuned threshold. That shapes the design: keep TF-IDF, add embeddings beside it, let the user see and compare both, and decide defaults from measurement in M7, not from this toy.

## Provider options (the owner chooses)
| | Local `fastembed` + `bge-small-en-v1.5` | Hosted embeddings API |
|---|---|---|
| Key / cost | None / free | Needs a key; small per-use cost |
| Privacy | Document text never leaves the machine | Chunk text is sent to the provider |
| Install | About 230 MB of packages, no PyTorch; model about 64 MB, downloaded once | None |
| Speed here | About 39 chunks/s; query 2 ms | Network latency per batch |
| Deploy (M7) | Host needs about 300 MB RAM and CPU for indexing | Simplest |
| Vector size | 384 | 1536 (or reduced) |

Recommendation: **local**, for privacy and zero cost, consistent with the project's "evidence-first, your data stays yours" stance.

## Design
**Retriever interface.** `Retriever.search(question, repo, doc_ids, top_k, min_score)` returning the same `Hit` shape; `TfidfRetriever` (today's code) and `EmbeddingRetriever`. The API takes `retrieval: "tfidf" | "embedding"` (default `tfidf` until M7 measures); responses say which was used. Scores are retriever-specific and not comparable.

**Embedder interface.** `Embedder` with `model_id`, `dimension`, `embed_passages`, `embed_query`; a real local implementation and a deterministic fake for offline tests. The model loads once, behind a lock, from a stable cache directory (the library's default is a temp folder that the OS may purge).

**Schema (migration 3).** `vector` extension; `embeddings(chunk_id, user_id, model_id, embedding vector(384), created_at)` with a composite foreign key `(chunk_id, user_id) -> chunks(id, user_id)` (needs `unique (id, user_id)` on chunks), RLS on, select/insert/delete only (immutable), cascade from chunks, so the existing ordered delete removes vectors too. No ANN index yet: each user's rows are few thousand at most and an exact scan filtered by `user_id` is both exact and simple; HNSW plus row filtering can silently return fewer results.

**Search function.** `match_chunks(query_embedding, match_count, document_ids)`: `SECURITY INVOKER` (runs with the caller's rights, so RLS applies), also filters `user_id = auth.uid()` explicitly, only `ready` documents, only rows with the matching `model_id`; `EXECUTE` revoked from `public` and `anon`, granted to `authenticated`. A `SECURITY DEFINER` version would bypass RLS and is forbidden here.

**Indexing.** After chunks are stored, embed them in batches and insert vectors; the document becomes `ready` only after that. Any failure runs the existing ordered delete. Documents uploaded before this step have no vectors: semantic search skips them and the response carries a notice ("N documents are not indexed for meaning search; upload them again").

**Abstention.** Embedding results pass a minimum cosine (`MIN_EMBEDDING_SCORE`), provisional and **untuned** (the toy data separates irrelevant at <= 0.48 from relevant at >= 0.59, which is anecdote, not evidence). M7 replaces it with a measured value.

**Frontend.** A "Search method" control (Keyword / Meaning) on the question form so the two can be compared on the same question; each answer says which method produced its evidence.

## Tests
Offline: embedder interface with a deterministic fake, batching, dimension and `model_id` guards, retriever selection, notice for un-embedded documents, failure cleanup removes vectors, frontend control. Real project (opt-in): two-user isolation for `match_chunks` (including calling it with the other user's document ids), anonymous calls refused, vectors deleted with the document, the real model ranks a paraphrase above an unrelated sentence. Mutation: switching the function to `SECURITY DEFINER` must fail the isolation test.

## Not in 6d
Hybrid ranking, reranking, HNSW, re-embedding on model change (the stored `model_id` makes that possible later), and tuning thresholds (M7).
