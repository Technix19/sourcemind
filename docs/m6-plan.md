# M6 plan: accounts, persistence, private files, vector search

Status: **proposal for review. Nothing here is implemented or applied yet.**
Decisions already made with the owner: dedicated Supabase project created by the owner; email + password sign-in; four sub-steps; embedding provider decided last (6d).

## Goal

Today every document lives in one process-wide dictionary: any visitor would see every document, and a restart loses everything. M6 makes data belong to a signed-in user, survive restarts, and be unreachable by anyone else, and it must be able to *prove* that.

## Core design decision: the API acts as the user, not as an admin

| | Option A: service key + filters in Python | **Option B (chosen): user's token + Row Level Security** |
|---|---|---|
| How | API uses the all-powerful service key and adds `WHERE user_id = ...` itself | API forwards the signed-in user's token to Supabase; Postgres applies RLS |
| If I forget a filter | Another user's data leaks | The database still refuses |
| Blast radius of a leaked key | Everything | Only what that user could already see |

Consequences: the service-role key is **not used in request handling at all**; the frontend key is the public "publishable/anon" key. It is safe to expose, but it is **not** powerless: it can do whatever the database allows an unauthenticated caller to do. Our protection is the combination of revoked default privileges and correct RLS policies, and this design grants the anonymous role nothing. The Python filters we write are a second layer, not the only one.

**Per-request identity (hard requirement).** Never store a user's token in a shared or global client: concurrent requests could then run with another user's identity. Each request builds its own Supabase/PostgREST call with that request's `Authorization` header, and **the token is verified before any document processing or paid model call**.

The in-memory store stays behind a small repository interface so unit tests remain fast; the Supabase-backed version is tested separately against the real project.

## Sub-steps

| Step | Delivers | Proven by |
|---|---|---|
| **6a** Schema, RLS, migrations, threat model | `supabase/migrations/*`, this document | Two-account isolation tests against the real database |
| **6b** Auth + persistence | Sign-in UI, API verifies tokens, documents/chunks stored per user, TF-IDF over stored chunks | API tests with two users; survives restart |
| **6c** Private files + "Open page" | Original file in a private bucket, short-lived signed links, citation opens the real page | Cross-user link test, delete removes the file |
| **6d** Embeddings + pgvector | Retriever interface with TF-IDF and embedding backends, same response schema | User-scoped vector search test; side-by-side on the same questions |

## Data model (6a)

`profiles`, `documents`, `chunks` now. `embeddings` arrives in 6d, `conversations / messages / message_citations` only if we choose to persist chat history (not required for M6). `evaluation_runs` is M7.

Design points worth knowing:

1. **Composite foreign key `chunks(document_id, user_id) -> documents(id, user_id)` (non-negotiable).** It requires `documents` to have `unique (id, user_id)`, which the draft has; a test must fail if either is removed. With RLS alone, a user could try to insert a chunk carrying *their own* `user_id` but *someone else's* `document_id`. The composite key makes the database itself reject any chunk whose owner differs from its document's owner, independent of RLS.
2. **Default deny.** RLS is enabled on every table; there are no policies for the anonymous role; privileges are revoked first and granted back narrowly (Supabase otherwise grants broad defaults).
3. **Chunks are immutable** (no update privilege or policy): re-indexing means delete and re-insert, so a citation can never silently change under a user.
4. **`user_id` defaults to `auth.uid()`** and every policy also checks it, so a client cannot choose someone else's id.
5. **Column-level update rights.** Users may update only `documents.name`, `status` and `storage_key`, never `user_id`, sizes or timestamps, so "re-assign this row to someone else" is refused by privilege before RLS is even consulted.
6. **`on delete cascade`** from user to documents to chunks (and embeddings in 6d). Storage objects are *not* covered by database cascades; the API deletes them explicitly (6c), and a failed file delete must not be silent.

### Recoverable deletion (6c)

Database and storage deletes are separate operations, so a crash between them must not leave orphans or leave deleted content searchable. Order:

1. Set `documents.status = 'deleting'` (hidden from lists and from retrieval).
2. Delete the document's chunks (and, from 6d, embeddings): its text is no longer retrievable from this point.
3. Delete the stored file (a missing file counts as success, so retries are safe).
4. Delete the `documents` row.

A document stuck in `deleting` is retried by a sweep (on startup and on demand) that resumes from step 2. Each step is idempotent. Test: simulate a failure after each step and assert the next attempt completes it.

Per-user limits (12 documents, 12 MB, 150 pages) stay enforced by the API. A database-level quota trigger is a possible hardening later.

## How isolation is tested (important)

The SQL Editor and the service key run with elevated rights and **bypass RLS**, so a check run there proves nothing about ordinary users. Isolation tests therefore use real sessions through the public API: **user A, user B, and an unauthenticated client**, each with its own token. They cover: reading, listing, deleting and updating the other user's rows; inserting chunks into the other user's document; forging or changing `user_id`; anonymous access; and tampered or expired tokens. A test must fail if RLS is switched off or a policy is removed (verified once by deliberately disabling RLS on a scratch table).

## Migration plan

- Files live in `supabase/migrations/` named `YYYYMMDDHHMMSS_description.sql`, forward-only, one concern per file, reviewed before applying.
- Applied only to the **new SourceMind project**, never to any other project in the connected account.
- Application route: you paste/run the SQL in that project's SQL Editor (or I apply it if the project is visible to my tools, after you confirm the project ref). Either way you review the exact SQL first.
- Rollback: each file is accompanied by a short "how to undo" note in its header; for a dev project the practical rollback is dropping the objects it created.
- Order: `…_core_schema.sql` (6a) -> storage bucket + policies (6c) -> `vector` extension + `embeddings` + search function (6d).

## Threat model (short)

Assets: document text and chunks, original files, embeddings, user accounts and tokens, the model API key, the owner's wallet (model usage).

| Threat | Mitigation | How we will verify |
|---|---|---|
| User A reads or deletes user B's documents by guessing an id (IDOR) | RLS `user_id = auth.uid()` on every table | Two-account test: B's id with A's token returns nothing / affects nothing |
| User A writes chunks into B's document | Composite FK plus RLS `with check` | Test: insert with B's `document_id` is rejected |
| User A forges ownership (`user_id` set to B on insert, or changed on update) | `with check` policies, `user_id` default `auth.uid()`, no column-update right on `user_id` | Tests: both attempts fail |
| Anonymous visitor reads anything | No anon privileges or policies | Test: anon key without a user token gets nothing |
| Forged or expired token | API verifies signature against the project's published signing keys, plus `exp`, `aud`, `iss` | Tests with tampered and expired tokens (exact settings confirmed once the project exists) |
| Leaked service key | Not used by the app; never in frontend; not needed by tests (test users are created through normal sign-up) | Grep and CI check that the key name appears nowhere in `apps/web` |
| Malicious document text (prompt injection) | Already handled in M4: text stays in the data channel, citations validated in code | Existing tests |
| XSS from document/model text | Everything rendered as React text, never HTML | Existing frontend test |
| Cross-user vector search | Search function runs as the caller (RLS applies) and also filters by user | 6d isolation test |
| Orphaned files after delete | API deletes the storage object; failure is surfaced and retried | 6c test |
| Signed link shared or leaked | A signed URL is a **temporary bearer credential**: anyone holding it can use it until it expires, so short expiry (about 60 s) limits exposure but does not bind it to the recipient. Private bucket; links issued only after an ownership check; never logged. Residual risk accepted and documented | 6c tests: user B cannot *create* a link for A's file, cannot read A's object path directly, and an expired link fails |
| Cost abuse (many questions with generation on) | Per-user rate and daily caps before any public launch | Required gate before deploying (M7) |
| Secrets or document text in logs | Log only ids and error types | Review plus tests that a provider error is not echoed (exists for M4) |
| Account abuse (weak passwords, sign-up spam) | Minimum password length in project Auth settings; email confirmation ON for anything public | Checklist before M7 deployment |

Known, accepted for the *development* project: email confirmation may be switched off so automated two-account tests can sign up instantly. It must be on before any public deployment.

## What the owner needs to do (before 6b; 6a SQL can be reviewed now)

1. Create a new Supabase project named e.g. `sourcemind` in your own account. Save the database password in a password manager.
2. Authentication settings: enable the Email provider; set minimum password length to at least 8; for the dev project turn "Confirm email" off.
3. Copy the **Project URL** and the **publishable (anon) key** into local, git-ignored env files only (`apps/api/.env`, `apps/web/.env.local`), never into chat or commits. Do **not** copy the service-role key anywhere.
4. Tell me the project ref (it is just an id). **Outcome:** the owner's project (`isinzkldtdqpqhmzeyqs`) is *not* visible to the assistant's connected tools (they list a different account), so the owner applies the migration and runs the tests locally, following `docs/m6a-apply.md`.

## Vector search security (6d)

Search must be exactly as protected as ordinary reads: the similarity function is `SECURITY INVOKER` (runs with the caller's permissions, so RLS applies), also filters by `user_id` explicitly, and has `EXECUTE` revoked from `anon` and `public` and granted only to `authenticated`. A `SECURITY DEFINER` search function would bypass RLS and is not allowed here.

## Review log

Changes made after an external review of this plan (all accepted): per-request client and verify-before-spend; composite FK made a hard requirement with a guard test; signed-URL wording corrected to "bearer credential"; recoverable deletion design; RLS tested only through real sessions; vector-search function rules; "publishable key" wording corrected. Additions beyond the review: column-level update rights, and deleting chunks *before* the file so removed content stops being searchable immediately.

## Open questions deferred to 6d

Embedding provider and model (hosted API: key and small per-use cost; or a local model: free but a multi-gigabyte download and slow on this machine), vector dimension, hybrid ranking, and whether to persist chat history.
