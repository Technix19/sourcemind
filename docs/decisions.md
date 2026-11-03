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
