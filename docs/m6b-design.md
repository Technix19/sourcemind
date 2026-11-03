# M6b design: sign-in and per-user persistence

Status: **6b-1 (backend) and 6b-2 (frontend) implemented and tested, including a real-browser run against the dev project.** Builds on `docs/m6-plan.md` (the API acts as the signed-in user; Row Level Security enforces ownership; schema and isolation tests are done in 6a).

## Facts checked against the real project (not assumed)

| Fact | Evidence | Consequence |
|---|---|---|
| Tokens are signed with **ES256** (asymmetric); one public key is published at `/auth/v1/.well-known/jwks.json`, cacheable 10 min, readable without any key | Fetched it; decoded a real token header | The API verifies tokens **locally and offline**. No secret is needed and there is no per-request call to Supabase. |
| Token claims: `iss = <project>/auth/v1`, `aud = authenticated`, `role = authenticated`, `sub` = user uuid, `exp`, `is_anonymous`, lifetime 3600 s | Decoded a real token | These are the exact values the verifier must require. |
| Auth as a FastAPI *dependency* lets the server **read the whole upload (8 of 8 MB) before rejecting** an unauthenticated caller; as a *middleware* in front it reads **0 bytes** | Measured on a throw-away app | Authentication is enforced by a gate in front of routing; the dependency only reads the result. |
| PostgREST returns at most a fixed number of rows per request (commonly 1000) | Known platform behavior, to be confirmed in tests | Reading a user's chunks **must page**; silently truncated results would make retrieval wrong. |

## Backend (6b-1)

**Auth gate (`app/auth.py`).** Middleware for every `/api/v1/*` route except `GET /api/v1/health`. It requires `Authorization: Bearer <jwt>` and verifies: algorithm is exactly `ES256` (never trust the token's own `alg`; rejects `none` and HS256 tricks), signature against the published key (looked up by `kid`; one rate-limited refetch if the `kid` is unknown, which handles key rotation), `exp`, `iss`, `aud`, `role == authenticated`, `sub` present, and `is_anonymous` not true. On success it puts `AuthUser(id, token)` on the request; on failure it returns 401 **before any body is read**. A route dependency `current_user` reads that and **also fails closed** if it is missing. A test enumerates every route and fails if one that is not on the explicit public list lacks protection.

**Per-request repository (`app/repository.py`).** One interface (`list`, `get`, `add`, `delete`, `chunks_for`, `count`) with two implementations:

- `SupabaseRepository(user)` built **per request** from that request's token (plain `httpx` calls to PostgREST with `apikey` + the user's `Authorization`), so no shared object can ever carry another user's identity. The service-role key is not used anywhere.
- `InMemoryRepository`, now **keyed by user id**, used by fast offline tests.

**Persistence flow.** Upload: validate (unchanged) -> insert document as `indexing` -> insert chunks in batches -> set `ready`. Any failure deletes the document (cascade removes its chunks), so no half-indexed document stays searchable; only `ready` documents are queried. The per-user 12-document limit is counted from the database.

**Query flow.** Fetch the caller's chunks (paged, selected documents only, `ready` only) -> existing TF-IDF -> existing answer flow. Known cost: every query downloads the user's chunks (megabytes at the limits). Acceptable for the MVP; measured and revisited in 6d/M7 when embeddings move search into the database.

**Config fails closed.** The API refuses to start without `SUPABASE_URL` and the public key. There is no "run without login" switch that could be deployed by accident. (Tests replace the auth and repository with fakes explicitly.)

**Out of scope for 6b:** password reset, email verification flows, OAuth, rate/cost caps (a required pre-launch gate in M7), original-file storage (6c), a database-level document quota trigger (possible later hardening).

## Frontend (6b-2)

`@supabase/supabase-js` session in the browser (it refreshes tokens itself); `AuthProvider`; a `/login` page (email + password, sign in / create account); `lib/api.ts` attaches the current access token to every call; a 401 signs the user out. A client-side guard redirects to `/login`, but it is only a convenience: **real enforcement is the server**. On sign-out or user change, **all in-memory state (documents, conversation, evidence) is cleared**, so the next person on a shared computer sees nothing. The sidebar shows the signed-in email and a sign-out button.

Known trade-off: the session token lives in browser storage, so an XSS bug could steal it. Mitigations already in place: everything renders as text, never HTML. Planned: a Content-Security-Policy header before any public deployment.

## Test strategy

**Offline (fast, default suite).** A throw-away ES256 key pair and a fake key set let us mint *any* token we like: valid, expired, tampered, wrong `iss`/`aud`, `role=anon` (the public key used as a token), missing `sub`, `is_anonymous`, unknown `kid`, `alg=none`, HS256 signed with the public key bytes. Also: unauthenticated upload returns 401 and reads no body; every route is protected unless allow-listed; two fake users cannot see each other's documents through the API; the paging helper handles exactly-one-page, many-page and empty results.

**Integration (real project, opt-in).** Real tokens from two accounts through the real app: A uploads and asks, B sees nothing and gets nothing back from queries, A's document survives a fresh app instance (persistence), a failed upload leaves no document behind, deleting removes the data.

**Existing 85 tests** keep working through an autouse fixture that installs a fake auth user and the in-memory repository; the new auth tests turn it off explicitly.

## Risks to watch
- Verifying with a cached key means a revoked or rotated key is honored for up to 10 minutes. Acceptable; documented.
- If the middleware is ever removed or reordered, the fail-closed dependency and the route-inventory test catch it.
- Chunk download per query will feel slow with large libraries; measure before optimizing.
