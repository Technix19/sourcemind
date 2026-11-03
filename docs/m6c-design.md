# M6c design: private original files, signed links, recoverable deletion

Status: **implemented and verified: 204 backend + 66 frontend offline tests, 34 real-project tests (owner applied the storage migration), and a real-browser run (Open page, signed link, page fragment, bytes identical, deletion).**

## Facts checked against the real project
- No bucket existed, and an ordinary user **cannot create one** (policy violation). So the bucket must come from a migration the owner applies, like the schema.
- Storage permissions are **policies on `storage.objects`**, a different table from our own. Inside those policies `documents` also has a column called `name`, so the object's name must be written `storage.objects.name`; an unqualified `name` would silently compare against the document's display name.

## Decisions
1. **Object names are ids only: `<user id>/<document id>`.** Never the user's filename (path tricks, leaks). The display name stays in the database.
2. **The upload policy requires an existing document row** whose `storage_key` equals the object name. So nobody can store files that no document owns (storage abuse), and the API creates the row first, then uploads.
3. **No update policy and `x-upsert: false`:** stored files are immutable, so a citation cannot silently point at different content.
4. **The Content-Type is chosen by us** (`application/pdf` or `text/plain`), never taken from the client, and the bucket itself only accepts those two types and 12 MB. An uploaded `.txt` containing HTML is served as plain text.
5. **Signed link, 60 seconds, per click.** Issued only after the user's own token passes the storage policy; `Cache-Control: no-store`; never logged; the frontend uses it immediately and never stores it. Honest limit: it is a bearer credential, so anyone who gets the URL can read the file until it expires.
6. **The tab is opened synchronously on click,** then pointed at the link when it arrives (browsers only allow pop-ups for the click itself). The new tab's `opener` is cut, and `#page=N` is added for PDFs only (the browser's viewer reads it; no server sees it).
7. **Deletion is ordered and resumable:** mark `deleting` -> delete chunks -> delete file -> delete row. Chunks go first so removed text is unsearchable immediately. A document stuck in `deleting` is finished automatically the next time that user lists their documents (no background worker, no admin key).
8. **Older documents** (uploaded before this step) have no stored file: the API says so clearly and the UI shows "File not stored" instead of a broken button.

## Rejected alternative: API streams the file (no signed URL)
Avoids bearer links entirely, but the API would carry up to 12 MB per view and the browser would need a blob URL. Kept as a possible later hardening if link leakage ever matters more than simplicity.

## Known limits
- **Deleting does not revoke a signed link that was already used.** Measured: the CDN caches a fetched file for the rest of that link's life (60 s), then it dies; a link never fetched dies at once. A test pins the bound ("cannot outlive its expiry even after deletion"). Reducing the lifetime shrinks this window.
- Orphans can still occur if the API process dies between creating the row and cleaning up; the stuck row is `indexing`, not `deleting`, so it is not swept yet. Worth handling in M7 (sweep stale `indexing` rows).
- No per-user storage quota beyond 12 files x 12 MB; a global cost cap is an M7 launch gate.
