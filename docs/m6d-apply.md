# Applying and testing M6d (meaning search)

Use **only the dedicated SourceMind Supabase project** (ref `isinzkldtdqpqhmzeyqs`). Migrations 1 and 2 must already be applied.

> **Until you do step 1, uploads fail** (HTTP 502, nothing is left behind): every upload now also stores vectors for meaning search.

## 1. Apply the migration

1. Dashboard -> **SQL Editor -> New query**.
2. Paste the whole of `supabase/migrations/20261103000003_embeddings.sql` and **Run**.
3. Expect "Success. No rows returned." (It enables the `vector` extension, adds an `embeddings` table and one search function. It is a one-time, forward-only migration: running it twice errors with "already exists", which is harmless.)
4. Check **Table Editor**: `embeddings` should appear with RLS enabled.

## 2. First run downloads the model once

The API loads a local model (`BAAI/bge-small-en-v1.5`, quantized, about 64 MB) the first time it needs it, into `~/.cache/sourcemind/models`. This happens in the background at startup, or on the first upload. After that it works offline, and **no document text is ever sent to a third party**. To switch meaning search off entirely, set `EMBEDDINGS_ENABLED=false` in `apps/api/.env` (documents are then indexed for keyword search only).

## 3. Run every real-project test

```bash
cd apps/api && source .venv/bin/activate
python -m pytest -m integration -v
```

Expected: **47 pass** (12 isolation + 9 API persistence + 13 file storage + 13 meaning search), in about 2 minutes. Any failure means a protection is not proven: send me the output.

## 4. Mutation checks (recommended; dev project only)

Break a protection, watch the matching test fail, restore it, and re-run.

| Break (SQL Editor) | Test that must fail | Restore |
|---|---|---|
| `alter function public.match_chunks(extensions.vector, integer, uuid[], text) security definer;` | `test_the_search_function_runs_as_the_caller_so_other_users_get_nothing` (another user suddenly sees your chunks) | `alter function public.match_chunks(extensions.vector, integer, uuid[], text) security invoker;` |
| `grant execute on function public.match_chunks(extensions.vector, integer, uuid[], text) to anon;` | `test_anonymous_callers_cannot_run_the_search_function` | `revoke execute on function public.match_chunks(extensions.vector, integer, uuid[], text) from anon;` |

Re-run the tests after each restore; all 47 must pass again.

## 5. Try it by hand

1. Start the API and web app, sign in, upload `data/sample/adaptive-practice-brief.pdf`.
2. Ask **"Which inputs does the model use?"** with **Search by: Keyword**. Expect "not enough evidence" (no shared words).
3. Ask the same with **Meaning**. Expect page-1 evidence ("correctness, execution time, attempts") with a "similarity" score.
4. Ask **"galaxies and nebulae"** with Meaning: expect "not enough evidence". This relies on a provisional threshold (`MIN_EMBEDDING_SCORE=0.5`) that is **untuned**: it works on this toy example and proves nothing in general.
5. Documents uploaded before this step show "Keyword only"; upload them again to enable meaning search.

## What the tests prove (and do not)

They prove, with real accounts: a user can only search, read and write their own vectors; the database function runs as the caller (so another user's document ids return nothing); anonymous callers cannot call it; vectors cannot be attached to someone else's chunks (the composite key stops it; a chunk that already has a vector is refused by the primary key), edited, or have the wrong size; only `ready` documents and vectors from the matching model are searched; deleting a document deletes its vectors; and the real model ranks a paraphrase above an unrelated sentence.

They do **not** prove that meaning search is *better*. That needs the labeled evaluation in M7. The toy experiment in `docs/experiments.md` showed a mixed picture: some vocabulary-mismatch misses recovered, one ranking error unchanged, and no natural "zero score" for unrelated questions.
