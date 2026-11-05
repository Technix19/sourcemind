# Re-capturing the UI

`ui-inventory.mjs` walks the whole app in a headless browser and rewrites the images and `INDEX.md` in the folder above.
Run it after UI changes to see the new state.

## One-time setup
```bash
mkdir ~/sourcemind-capture && cd ~/sourcemind-capture
npm init -y && npm i playwright-core
npx playwright install chromium            # or set CHROMIUM_PATH to any Chromium/Chrome executable
```

## Run
Start the API and the web app first (see the main README). Then:
```bash
node /path/to/sourcemind/docs/ui-screenshots/capture/ui-inventory.mjs \
  /path/to/sourcemind/apps/api/.env  /path/to/sourcemind/docs/ui-screenshots  /path/to/sourcemind/data/sample/adaptive-practice-brief.pdf
```
Optional: `WEB_URL`, `API_URL`, `CHROMIUM_PATH` environment variables.

## What it needs and does
- The first argument is `apps/api/.env`; it reads the two test-account lines (`SUPABASE_TEST_USER_A_EMAIL` / `_PASSWORD`, see `docs/m7c-test-accounts.md`). It never prints or stores them.
- It signs in as that account, uploads the sample PDF, asks four questions (one with a real generated answer, which costs a fraction of a cent if `ANTHROPIC_API_KEY` is set), and **deletes the test document at the end**. It also empties that account's documents at the start.
- The signed-in email is masked in every image (any text or label containing the test account's address is replaced) and the dev-only Next.js indicator is removed.
- Light theme is captured everywhere (the browser is pinned to light so results are repeatable); a smaller dark-theme set is captured by clicking the theme switch.
- It deletes nothing except those test documents. **Delete the output folder's old images yourself** if you want a clean slate; the script overwrites files with the same names.
