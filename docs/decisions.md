# Decision log

## ADR-001: TF-IDF before embeddings (M3)
Chosen as an inspectable baseline we can measure later against semantic search. Known failures (ranking by overlap, vocabulary mismatch) are recorded in `experiments.md`. The relevance threshold is an untuned guess until M7.

## ADR-002: Grounding is enforced in code, not in the prompt (M4)
**Decision:** after the model answers, we strip citations that don't map to evidence we sent, withhold answers with no valid citation, and fall back to sources-only on any failure.
**Why:** prompt instructions are requests; a model can ignore them, and document text can try to override them. Code checks cannot be talked out of it.
**Limits:** a valid `[1]` proves the answer points at real evidence, not that the sentence is actually supported by it. Measuring that (faithfulness) is M7 work.

## ADR-003: Generation is opt-in and provider-isolated (M4)
Default mode is `sources_only`; generation needs a key AND a model name (no guessed default). Everything provider-specific lives in `app/llm.py` behind a two-line interface, so a different provider is a one-file change and tests use a fake model.

## ADR-004: Evidence returned equals evidence sent (M4)
If the context budget drops chunks, they are also dropped from the response. That way every citation number the user sees maps to exactly what the model saw.

## ADR-005: The API acts as the signed-in user, so the database enforces isolation (M6, proposed)
**Decision:** the backend forwards the user's token to Supabase and relies on Row Level Security; the service-role key is not used in request handling. Python-side filters remain as a second layer.
**Why:** with a service key, one forgotten filter leaks every user's data; with RLS the database refuses regardless. It also makes isolation testable as a property of the database (two-account tests).
**Cost:** slightly more setup, and tests need a real Supabase project. Details and threat model: `docs/m6-plan.md`.

## ADR-006: Deleting a document is a recoverable, ordered process (M6, proposed)
**Decision:** mark `deleting`, delete chunks (and embeddings), delete the stored file, then delete the row; a sweep resumes any document stuck in `deleting`.
**Why:** database and storage deletes cannot be one transaction. Deleting chunks first makes removed content unsearchable immediately, and idempotent steps make crashes safe to retry.

## ADR-007: Authentication is a gate in front of routing, not only a FastAPI dependency (M6b-1)
**Decision:** a middleware verifies the token before routing; the route dependency only reads the result and also fails closed.
**Why (measured, not assumed):** with auth as a dependency, the server read the entire 8 MB upload before rejecting an anonymous caller; with the gate it read 0 bytes. A test now repeats that measurement against the real app.
**Related choices:** verify tokens offline against Supabase's published ES256 key (no secret, no per-request call); accept only ES256; refuse the public key, anonymous users and the service role; cache keys 10 minutes and refetch an unknown key at most every 30 s; a key-server outage is a 503, not a misleading 401.

## ADR-008: No anonymous mode; configuration fails closed (M6b-1)
**Decision:** the API refuses to start without Supabase settings, and there is no switch that disables login.
**Why:** a "no-login for local demos" flag is exactly the kind of setting that ends up deployed. Offline tests use explicit fakes instead of a production bypass.

## ADR-009: Per-user state lives under providers keyed by user id (M6b-2)
**Decision:** documents, conversation and evidence providers are remounted whenever the user id changes or the user signs out; private pages are never rendered while the session is loading or absent.
**Why:** clearing state by hand is easy to forget; remounting destroys it by construction, so the next person on a shared computer sees nothing. A token refresh keeps the same id and so keeps the state. The client guard is only a convenience: the API still rejects every unauthenticated call.
**Also:** sign-out uses `scope: "local"` so it ends only this browser's session, not every device.

## ADR-010: Original files are served by short-lived signed links, not proxied (M6c)
**Decision:** the API issues a 60-second signed link only after ownership is proven by the user's own token; the browser fetches the file straight from storage.
**Why:** simple and cheap (no 12 MB through the API) and it matches the blueprint. **Cost:** a signed URL is a bearer credential, so anyone holding it can read the file until it expires. Mitigations: short life, per-click issue, no-store, never logged or stored, new tab cut off from the app. **Measured:** the CDN caches a fetched file for the rest of the link's life, so deleting a document does not revoke a link already used until it expires (60 s); the lifetime is the lever. Streaming through the API is the documented alternative if this ever matters more.

## ADR-011: Storage names are ids, uploads require an owning row, files are immutable (M6c)
**Decision:** object name `<user id>/<document id>`; the upload policy requires a document row pointing at that name; no update policy and no upsert; the Content-Type is chosen server-side.
**Why:** no user-controlled path or type reaches storage, no orphan files can be created, and a citation can never change underneath the user.
