# Applying and testing the M6a schema (owner checklist)

Use **only the dedicated SourceMind Supabase project** (ref `isinzkldtdqpqhmzeyqs`). Do not run this in any other project.

## 1. Project settings (once)

1. Authentication -> Providers: **Email** enabled.
2. Authentication -> Sign In / Providers (or Policies): minimum password length **8 or more**.
3. **Dev project only:** turn **"Confirm email" off**, so the tests can create two users instantly. Turn it back **on** before any public deployment.

## 2. Apply the migration

1. In the dashboard open **SQL Editor -> New query**.
2. Paste the whole contents of `supabase/migrations/20261103000001_core_schema.sql` and press **Run**.
3. Expect "Success. No rows returned." If you see an error, stop and send it to me; do not edit the SQL by hand.
4. Check: **Table Editor** should list `profiles`, `documents`, `chunks`, each marked with RLS enabled. (If a table shows "RLS disabled", something went wrong.)

Running the file twice fails ("already exists"); that is expected and safe. It is a one-time, forward-only migration.

## 3. Local credentials (never in chat or git)

In **Project Settings -> API** copy the **Project URL** and the **publishable (anon) key**. Put them in `apps/api/.env`:

```
SUPABASE_URL=https://isinzkldtdqpqhmzeyqs.supabase.co
SUPABASE_ANON_KEY=<publishable key>
```

Do **not** copy the `service_role` / secret key anywhere. The tests and the app never need it.

## 4. Run the isolation tests

```bash
cd apps/api && source .venv/bin/activate
python -m pytest -m integration -v
```

Each run signs up two new throw-away test users (`sourcemind-test-…@example.com`) in the dev project. They are harmless; you can delete them later under Authentication -> Users.

Expected: 12 tests pass. **Any failure means isolation is not proven**: send me the output. Do not move on to 6b.

## 5. What the tests prove (and do not)

They prove, through real user sessions: anonymous callers get nothing; a user cannot read, update, delete or create rows belonging to another user; ownership cannot be forged or reassigned; chunks cannot be attached to someone else's document (composite foreign key); chunks are immutable; deleting a document removes its chunks; a tampered token is rejected.

They do not yet cover: expired tokens (needs the signing key), signed file links (6c), vector search (6d), or the API's own token verification (6b).
