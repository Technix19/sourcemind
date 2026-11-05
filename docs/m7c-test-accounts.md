# Test accounts for the real-project tests

The real-project tests (`python -m pytest -m integration`) need two signed-in users. They used to create a
throwaway user per run, which only works while **Confirm email** is off. With confirmation on (as it should be
for any real deployment), sign-up returns no session, and creating throwaway users would also send real emails
to made-up addresses through your SMTP provider (bounces damage a sender's reputation).

So the tests sign in to two fixed accounts instead. No service-role key is involved.

## One-time setup
1. In the running app, create two accounts with addresses you control. A `+` alias works with Gmail:
   `you+sourcemind-a@gmail.com` and `you+sourcemind-b@gmail.com`. Use a strong, unique password for each.
2. Click the confirmation link in each email.
3. Add these four lines to `apps/api/.env` (git-ignored; never commit them):
   ```
   SUPABASE_TEST_USER_A_EMAIL=you+sourcemind-a@gmail.com
   SUPABASE_TEST_USER_A_PASSWORD=...
   SUPABASE_TEST_USER_B_EMAIL=you+sourcemind-b@gmail.com
   SUPABASE_TEST_USER_B_PASSWORD=...
   ```
4. Run `python -m pytest -m integration`.

## Notes
- Use these accounts only for tests. The tests delete the documents they create, but a crashed run can leave a
  few behind; if uploads start failing with "Document limit reached", sign in as that user and delete them.
- Without these variables the tests fall back to throwaway sign-ups, which need **Confirm email** off in a
  development project. Never turn it off in a project that real users can reach.
