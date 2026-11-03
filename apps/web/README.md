# SourceMind web app

Next.js (App Router) + TypeScript + Tailwind frontend for the SourceMind API. See the [project README](../../README.md) for setup and status.

```bash
npm install
npm run dev     # http://localhost:3000 (start the API first)
npm test        # unit and component tests
npm run lint
npm run build
```

Structure: `app/` routes, `components/` (`layout`, `documents`, `chat`), `lib/` (typed API client, helpers). No secrets belong here; `NEXT_PUBLIC_API_URL` is only a URL.
