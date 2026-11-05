# Data handling and retention

What SourceMind stores, where, for how long, and who can see it. Written from the code and migrations as of
2026-11-05. Items marked **not verified** are things I did not test or could not see from this project.

This is a portfolio project, not a compliance document. It makes no promise about legal requirements
(GDPR and similar). Do not upload confidential or regulated documents.

## What is stored

| Data | Where | Who can read it | Kept until |
|---|---|---|---|
| Email address and password hash | Supabase Auth | You (your session); the project owner via the Supabase dashboard | The account is deleted in the dashboard (no self-service deletion yet) |
| Your uploaded files (original PDF/TXT/MD) | Private Supabase Storage bucket, named by ids | You, through 60-second signed links the API issues only for your own documents | You delete the document |
| Extracted text, split into chunks | Postgres (`chunks`), protected by Row Level Security | Only you, as enforced by the database | You delete the document |
| Meaning-search vectors | Postgres (`embeddings`, pgvector) | Only you | You delete the document (they are removed with the chunks) |
| Document names, sizes, page counts | Postgres (`documents`) | Only you | You delete the document |
| Your questions and answers | **Not stored.** They exist in the page's memory and are gone on reload | n/a | Closing or reloading the tab |
| Your sign-in session | Your browser (supabase-js keeps it so you stay signed in) | Your browser | You sign out, or it expires |
| Rate-limit counters | The API server's memory (user id plus timestamps) | The server process | A restart, or 24 hours at most |

There is no automatic expiry: your documents stay until you delete them.

## Deleting a document

Deleting is ordered so it can be retried after a crash: the document is hidden first, then its chunks and vectors,
then the stored file, then the row. If the server stops partway, the document stays hidden and the next time you
open your library the cleanup finishes. An upload that was interrupted (stuck "indexing" for 15 minutes) is removed
the same way.

Two honest limits:
- A signed link you already used is cached by the storage CDN until it expires (60 seconds), so a deleted file can
  stay fetchable by anyone holding that link for up to a minute.
- **Not verified:** whether Supabase keeps backups or point-in-time copies of deleted rows or files on your plan.
  Check your project's plan; this project does nothing to purge backups.

## Deleting an account

There is no account-deletion feature. As the project owner you can delete a user in the Supabase dashboard, and
the database removes their profile, documents, chunks and vectors automatically. **Not verified:** what happens to
that user's files in the storage bucket, because storage objects are not deleted by a database cascade, and I did
not test deleting a user who still has files. Delete the user's documents in the app first.

## What leaves your machine, and where it goes

- **Always:** your documents and questions go to your Supabase project (database and storage), hosted by Supabase.
  Sign-in emails (confirmation links) are sent through the SMTP provider you configured (Brevo), which sees the
  recipient address.
- **Meaning search:** the embedding model runs on the API server itself. No document text goes to a third party for
  this.
- **Generated answers (off by default):** when `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` are set and a user asks for
  a generated answer, the question and the retrieved excerpts are sent to Anthropic. The app does not store the
  request or the response. How Anthropic retains API data depends on its terms and your account; check them before
  using confidential material (**not verified** here).
- Nothing is sent to analytics or advertising services; the app includes none.

## What is logged

The API logs error types and HTTP statuses, for example "storage error status=500", "rejected token: ExpiredSignatureError"
and "rate limited bucket=queries". It does not log tokens, signed links, document text, questions, answers, filenames or
user ids. Signed links are never stored. Your host or platform may keep its own request logs (URLs, IP addresses);
**not verified**, because the API has not been deployed anywhere yet.

## Access by the project owner

The owner of the Supabase project can read everything in it through the dashboard, including every user's documents
and chunks. Row Level Security protects users from each other, not from the person who runs the database. Do not
treat this as end-to-end encrypted.
