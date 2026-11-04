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

## ADR-012: Meaning search is local, separate from keyword search, and never the silent default (M6d)
**Decision:** a local ONNX model (`bge-small-en-v1.5`, 384 dimensions) produces vectors stored in pgvector; keyword (TF-IDF) stays the default; the user chooses the method, and every answer says which one found its evidence.
**Why:** a measured toy experiment showed embeddings help vocabulary mismatch but do not fix every ranking error and never score zero, so "better" is unproven until M7. Local means no cost, no key and no document text leaving the machine.
**Safety choices:** the search function is `SECURITY INVOKER` (a `SECURITY DEFINER` one would bypass Row Level Security), filters on the caller's id as well, and has execute revoked from `anon`; vectors are immutable and tied to their chunk's owner by a composite foreign key; no ANN index yet (exact scan per user is simpler and cannot silently return fewer rows).
**Known limits:** the relevance threshold for meaning search (0.5) is provisional and untuned; documents uploaded before this step have no vectors and are reported, not silently skipped; indexing adds roughly 10 s per 400 chunks on an M2.

## ADR-013: Evaluation labels are mechanical and the test split is scored once (M7a)
**Decision:** a page is relevant to a question if any of the question's literal answer phrases appears on it; unanswerable questions list terms that must be absent from the topical document; the dataset is split (stratified, fixed seed) into dev and test, thresholds and design are tuned on dev only, and test is scored once with an explicit `--final` flag.
**Why:** hand-picked page numbers drift and miss facts repeated across pages (the Constitution edition repeats provisions in its index); a validator on mechanical labels caught six errors in my own first draft (too-broad absence checks, a phrase split by the PDF's two-column layout, and a question the corpus could in fact answer). Tuning and reporting on the same questions would overstate quality.
**Also:** the evaluation reuses the product's chunker, TF-IDF class and embedder, with a parity test that the harness ranks exactly as the product does; every metric carries a bootstrap interval because a few dozen questions cannot support point estimates.

## ADR-013 addendum: dev/test labels are frozen in the data (M7a)
**Found:** adding ten questions to a stratified shuffle would have moved three already-examined questions (`fed-06`, `sleep-04`, `sleep-05`) into the held-out test half. Nothing had been scored on test, but the scheme was fragile.
**Decision:** each question stores its own `split`; batch 1 keeps the assignment whose development results were examined (guarded by a regression test); new questions are labeled once and never move; an unlabeled question falls back to a per-question hash that cannot depend on other questions.
**Also recorded:** the dataset has a single author (the assistant), because the owner chose not to write blind questions. That limits what the evaluation can claim, and the report will say so.

## ADR-014: Pre-registered analysis, one scored test run, and a recommendation that stays a judgment call (M7b)
**Decision:** the analysis rules (balanced accuracy for thresholds, median of ties, a 0.10 margin to change chunk size, "default stays keyword unless the evidence says otherwise") were written on 2026-11-04 before any tuning. Thresholds were tuned on the dev split only, the setup was committed (`0db61d1`), and the 19-question test split was scored once with `--final`. The failure analysis was written afterward and says so.
**Result (test split, 15 answerable, 4 unanswerable):** Recall@3 was 0.60 for keyword and 0.87 for meaning, with intervals 0.33 to 0.80 and 0.67 to 1.00. They overlap, so **no difference is demonstrated**. Meaning met the pre-registered condition for *recommending* a change, which is why the report calls it a judgment call and not a win.
**Found:** the tuned keyword threshold (0.25) refused 67% of answerable questions. The product defaults (0.05 and 0.5) rarely abstain, which is also poor on the 4 unanswerable questions. Neither setting is good, and four questions cannot settle it.
**Not done on purpose:** no product default was changed. The label gap for `con-04` (index pages restating the answer with different punctuation) is documented in the failure analysis, not relabeled after seeing results.
**Results page:** the API serves the published JSON at `GET /api/v1/evaluation/latest` (login required, 404 until published). The page writes every number out with its interval; the bars are decorative and `aria-hidden`. It shows caveats before numbers and has no placeholder values.

## ADR-015: Rate limits are per verified user, in memory, and fail toward protection (M7c-2)
**Decision:** a gate placed just after authentication counts requests per user id in three buckets (questions, uploads, everything else), and a rolling 24-hour cap limits paid model calls. Over the cap, generation falls back to showing evidence instead of failing the request. Invalid or non-positive settings fall back to the defaults, never to "unlimited".
**Why:** the expensive work (PDF parsing, embedding, model calls) is only reachable by signed-in users, so the user id is the right key and cannot be dodged by changing IP. Running before routing means a refused upload is never read. Failed model calls count, because a provider can bill for them. Refused attempts are not recorded, so hammering does not lengthen the wait.
**Cost:** counters are in memory. They reset on restart and are per process, so several instances would each allow the full limit. That is acceptable for one small host and is stated in the README; the upgrade is a shared store (for example a Postgres table).
**Not covered:** unauthenticated floods (they are rejected cheaply by offline token checks, but a host-level limit is still advisable), and a global spending ceiling across all users.
