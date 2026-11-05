# M7d: Deployment plan

Status: **plan only. Nothing has been created, deployed or made public.** Every step that creates something, spends money
or exposes the app needs the owner's explicit yes first. Written 2026-11-05.

## 0. Decisions (owner, 2026-11-05)

The owner first chose option C (no hosting), then changed to **Vercel (web) plus Render's free plan (API)**. Recorded answers:

| Question | Answer | Consequence |
|---|---|---|
| Render plan | **Free** (512 MB RAM, 0.1 CPU) | Meaning search cannot run (needs about 600 MB), so the hosted API is **keyword-only** (`EMBEDDINGS_ENABLED=false`); it spins down after 15 idle minutes and takes about a minute to wake |
| Sign-ups | **Open** (recommended was invite-only) | Strangers can register; email confirmation stays on; add a CAPTCHA in Supabase; storage and email limits are exposed |
| Generated answers | **On** (recommended was off) | Costs money; per-user cap (20/day) plus a **new server-wide ceiling** (`GLOBAL_DAILY_GENERATIONS`, default 200 per rolling 24 hours); the owner sets a spend limit in the Anthropic Console first |
| Supabase project | **Reuse the current project** (recommended was a new one) | Test accounts and about 50 leftover throwaway test users share the project with the public demo; clean the throwaway users before going public |
| Who creates the Render service | The assistant, via the Render connector, after an explicit go | Secrets typed by the owner in the dashboard; Vercel done by the owner |

Two limits to keep in mind: on the free plan every spin-down resets the in-memory rate-limit counters, so the caps hold while the
service is busy but reset after it has been idle; and the cold start means the first request after idle can take about a minute.

## 1. Facts this plan rests on

### Measured on the owner's Mac (Apple M2, Python 3.10), not estimated

| What | Peak memory |
|---|---|
| The API process after importing the app | about 147 MB |
| After loading the embedding model | about 360 to 500 MB |
| While embedding 400, 1,000 and 2,000 chunks (batched) | about 540, 550 and 565 MB |

So with meaning search on, the API needs **about 600 MB at peak: a host with 512 MB of RAM cannot run it, and 1 GB is the
practical floor.** With `EMBEDDINGS_ENABLED=false` (keyword search only) the process stays near 150 MB.

Speed: about 35 to 40 chunks per second on this Mac (400 chunks in 10 s, 2,000 in 58 s). **Not measured: speed on a small
cloud CPU**, which will be slower. An upload embeds synchronously inside the request, so a 150-page PDF could take minutes
on a small host. Measure this on the real host before inviting anyone.

### From the providers' own pages (read 2026-11-05; confirm before you pay)

| Provider | Fact | Source |
|---|---|---|
| Render | Web service sizes: Free 0.1 CPU / 512 MB, Starter 0.5 CPU / 512 MB, **Standard 1 CPU / 2 GB**, Pro 2 CPU / 4 GB | render.com/docs/compute-plans |
| Render | Free services spin down after 15 minutes idle; the next request takes about a minute; 750 free hours per month; single instance only; ephemeral disk; outbound ports 25/465/587 blocked | render.com/docs/free |
| Render | Python and Dockerfile deploys supported; zero-downtime deploys and health checks exist | render.com/docs/web-services |
| Render | Prices: Starter about $7 and Standard about $25 per month. **Unconfirmed**: these came from search snippets; the official pricing page did not load | check render.com/pricing |
| Supabase Free | 500 MB database, 1 GB file storage, **pauses after 1 week of inactivity, no backups** | supabase.com/pricing |
| Supabase Pro | From $25 per month; daily backups kept 7 days | supabase.com/pricing |
| Vercel Hobby | Free, but **non-commercial, personal use only**; functions run up to 300 s | vercel.com/docs/plans/hobby |

## 2. Options

| | A. Full demo | B. Cheap keyword-only demo | C. No hosting |
|---|---|---|---|
| Web | Vercel Hobby | Vercel Hobby | none |
| API | Render Standard (2 GB) | Render Starter or Free, `EMBEDDINGS_ENABLED=false` | local only |
| Search | keyword and meaning | keyword only | both, locally |
| Cost (to confirm) | about $25 per month, plus Supabase | $0 to about $7 per month, plus Supabase | $0 |
| Main drawbacks | Monthly cost; slow embedding on 1 CPU is unmeasured | The better-on-paraphrases feature is off; Free spins down and restarts in about a minute | Reviewers cannot try it |

**Recommendation: A, with controlled access (see 3.1), switched on only for a review period, and C's materials
(README, screenshots, a short recorded walkthrough) kept as the always-available fallback.** B is a fair choice if cost is
the constraint, but the evaluation's one clear weakness (paraphrases) is exactly what meaning search addresses, so B
demonstrates the weaker product. The final choice is the owner's.

## 3. Gaps to close before anything goes public

### 3.1 Decisions only the owner can make
1. **Who can sign up.** Open sign-up on a public URL invites abuse: each account can store 12 documents of up to 12 MB
   (up to 144 MB), so about seven accounts fill the free 1 GB of storage. Options: turn off public sign-ups and create
   reviewer accounts by hand (simplest, safest); or keep sign-up with a CAPTCHA (Supabase supports one) and email
   confirmation. **Recommended: invite-only.**
2. **Generated answers on the public demo?** The per-user caps do not bound the *total* bill, and there is no global
   ceiling in the code. **Recommended: leave generation off publicly** (the deployed API simply has no
   `ANTHROPIC_API_KEY`), or enable it only for invited accounts with a spend limit set in the Anthropic Console.
3. **One Supabase project or two.** Today the real-project tests and the app share one project, so test users and test
   documents live next to real ones. **Recommended: a second project for the public demo**, keeping the current one for
   development and tests. The free plan allows it; the migrations are in `supabase/migrations`.
4. **Free-tier Supabase tradeoffs:** a demo project pauses after a week without use and has no backups. Accept that, or
   pay for Pro ($25 per month) if the demo matters.

### 3.2 Repository work (safe; I can do this without touching any outside service)
- A `Dockerfile` (or Render native build command) with a **pinned Python version**, the start command, and a health check
  on `/api/v1/health`.
- **The embedding model download (about 64 MB) must not happen on every start**: the disk is ephemeral, so either bake
  the model into the image or accept a download after every restart. This also affects the first meaning-search query
  after a cold start.
- A `render.yaml` (or documented dashboard settings) that pins **one instance**: the rate limits live in memory, so more
  than one instance would multiply every limit.
- A deployment checklist in the README; update `docs/data-handling.md` with the real hosts once chosen.
- Remove the stray empty tracked file `apps/api/401` (looks like an accidental shell redirect).
- Check the response header `Cross-Origin-Resource-Policy: same-site` with the web app and API on different domains
  (they will be: vercel.app and onrender.com). CORS fetches should be unaffected, but this must be verified in a browser,
  not assumed.

### 3.3 Configuration (names only; values never go in the repo or in chat)

| Where | Variable | Notes |
|---|---|---|
| API host | `APP_ENV=production` | turns the interactive docs off |
| API host | `FRONTEND_ORIGIN` | the exact web URL, nothing else |
| API host | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | the **demo** project (public key only; never the service-role key) |
| API host | `EMBEDDINGS_ENABLED` | `true` on a 2 GB host |
| API host | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | only if generation is on; this is a secret |
| API host | `RATE_*`, `DAILY_GENERATIONS`, `STALE_UPLOAD_MINUTES` | defaults are fine to start |
| Web host | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **build-time**: set them before the first build, because the Content-Security-Policy is derived from them |
| Supabase | Site URL and Redirect URLs | the real web URL, or confirmation emails link to the wrong place |
| Supabase | SMTP (Brevo) | already set in the current project; repeat for the demo project |

## 4. Order of work, with a confirmation at every outward-facing step

0. **Decisions** (3.1): the owner answers; I record them in this file.
1. **Repository work** (3.2): I do it and show the diff. No outside effects.
2. **Create the demo Supabase project and apply the three migrations** (owner, in the dashboard, or by me with a clear yes).
3. **Create the API service** on the chosen host. *Costs money starting here.* Secrets are typed into the host's dashboard by the
   owner. I never see them.
4. **Deploy the web app** on Vercel (the Vercel connector here is not authorized; the owner can do this in the Vercel
   dashboard, or authorize the connector first). Turn on Vercel's deployment protection for preview URLs.
5. **Wire the URLs**: `FRONTEND_ORIGIN`, Supabase Site URL and Redirect URLs, `NEXT_PUBLIC_API_URL`; redeploy the web app.
6. **Smoke test** (checklist below), with the browser console open.
7. **Open access** to the chosen reviewers only after step 6 passes.
8. **Watch for 24 hours**: the host's memory and restart count, request errors, Supabase usage, and (if generation is on) the
   Anthropic Console spend.

### Smoke test checklist
- Health check returns `status: ok` and `generation_available` matches what you intended.
- `/api/docs` and `/openapi.json` return 404.
- Sign up (or accept an invite), confirm by email, sign in.
- Upload a small PDF; ask a question under Keyword and under Meaning; open a citation page.
- **Upload the largest document you intend to allow and time it**; this is the unmeasured risk above.
- Open the Evaluation page; check the browser console for any Content-Security-Policy violation on every page.
- Exceed a rate limit on purpose and see the 429 message.
- Delete a document; confirm it disappears and its file link stops working.
- Restart the API; confirm it comes back healthy and meaning search still answers (model reload).

## 5. Rollback and teardown
- **Rollback:** redeploy the previous Vercel deployment and the previous API revision. Supabase migrations only move
  forward; do not apply new ones to the demo project during the review period.
- **Pause fast:** suspend the API service (stops the compute bill) or remove the host's environment variable
  `ANTHROPIC_API_KEY` to stop model spend immediately; revoke the key in the Anthropic Console to be sure.
- **Teardown:** delete the Render service, the Vercel project and the demo Supabase project. Deleting a Supabase
  project removes its database and stored files. Delete reviewer accounts first if you want a clean record.

## 6. What this plan does not cover
No custom domain, no uptime monitoring or alerting, no backups policy beyond what the Supabase plan provides, no load
testing, no legal review of storing other people's documents, no plan for sharing a deployed demo beyond invited
reviewers.
