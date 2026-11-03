# Applying and testing M6c (private original files)

Use **only the dedicated SourceMind Supabase project** (ref `isinzkldtdqpqhmzeyqs`).

> **Until you do step 1, uploads fail** (HTTP 502, nothing is left behind). The API now stores each
> original file in a private bucket, and that bucket is created by this migration.

## 1. Apply the migration

1. Dashboard -> **SQL Editor -> New query**.
2. Paste the whole of `supabase/migrations/20261103000002_private_storage.sql` and **Run**.
3. Expect "Success. No rows returned."
4. Check **Storage** in the dashboard: a bucket named `documents` should exist and be marked **Private**.

(It can be run twice: the bucket insert is an upsert. The three policies would error with "already exists" on a second run; that is harmless.)

## 2. Run every real-project test

```bash
cd apps/api && source .venv/bin/activate
python -m pytest -m integration -v
```

Expected: **34 pass** (12 isolation + 9 API persistence + 13 file storage). Any failure means a protection is not proven: send me the output.

## 3. Mutation checks (recommended; dev project only)

A passing test only means something if it can fail. Break one protection, watch the matching test fail, restore it.

| Break (SQL Editor) | Test that must fail | Restore |
|---|---|---|
| `update storage.buckets set public = true where id = 'documents';` | `test_the_bucket_is_private_so_public_urls_do_not_work` | `update storage.buckets set public = false where id = 'documents';` |
| `drop policy documents_objects_select_own on storage.objects;` | `test_storage_is_set_up_and_an_upload_stores_the_original_file` (nobody can read their own file) | re-run the policy from the migration file |

Re-run the tests after each restore; all 34 must pass again.

## 4. Try it by hand

1. Start the API and web app as usual and sign in.
2. Upload the sample PDF (`data/sample/adaptive-practice-brief.pdf`), ask a question, and press **Open page ->** on an evidence card: the PDF opens in a new tab at that page.
3. In **Documents**, press **Open** on the same file.
4. Documents uploaded *before* this step show "File not stored"; upload them again to enable opening.

## What the tests prove (and do not)

They prove, with real accounts: the bucket is private; only the owner can obtain a signed link, and a link stops working after it expires; other users cannot read, replace or delete a file, write into someone else's folder, or create files with no owning document; stored files cannot be overwritten; the bucket itself rejects wrong types and oversize files; deleting removes the file, chunks and row; an interrupted deletion hides the document and is finished automatically.

They do **not** prove: that a link you have already handed out stays private (a signed link is a bearer credential: whoever holds it can read the file until it expires, 60 seconds here), or anything about browsers' PDF viewers.

### Measured: deleting does not revoke a link that was already used
Found with a real browser run, then measured: Supabase's CDN caches a file's bytes per signed link. A link that was **fetched before** the document was deleted keeps serving the file until **that link's own expiry** (the response's `Expires` header; 60 s in this app), then dies (measured: HIT for about 52 s, dead at 62 s). A link that was never fetched dies the moment the file is deleted. So the worst case after deleting a document is: someone who already opened a link in the last 60 seconds can still re-fetch it for the remainder of those 60 seconds. This is why the lifetime is short; do not lengthen it without weighing this.
