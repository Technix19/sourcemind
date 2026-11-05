# Public landing page

The SourceMind homepage (\`/\`) is now public. The authenticated document-research application
is at \`/workspace\`; documents and evaluation stay at their existing routes.

The landing is intentionally scoped to:
- Hero and a stylized product-preview illustration
- Short explanation of the three-step research workflow
- Feature descriptions grounded in implemented functionality
- FAQ covering supported files, citation links, source-only mode, privacy and limitations
- CTA to the real application and a concise footer

The screenshot-like hero preview is **illustrative UI**, not an assertion that the
underlying content is a genuine user's document or an exact screenshot.
It uses an example from the existing demo document and is marked as an illustration.

Excluded on purpose: testimonials, ratings, pricing, trust logos, invented customer
counts and legal-policy links without real destinations.

## App routing

- \`/\` — public landing page; signed-out visitors can access it without authentication
- \`/login\` — existing sign-in and sign-up experience
- \`/workspace\` — private Ask Questions workflow (previously \`/\`)
- \`/documents\` — private document library
- \`/evaluation\` — private retrieval evaluation dashboard

The AppGate continues to require authentication on every private route. Visitors
opening \`/workspace\` without a session are redirected to \`/login\`; upon sign-in they
arrive at \`/workspace\`. The API remains the authoritative security boundary.

## Design and content decisions

Based on the four-page user-provided SaaS landing-page screenshot template:
centered hero + product illustration; features; short process; FAQ; minimal footer.
The original template's team, testimonials, customer logos and three-tier pricing were
omitted because they aren't relevant or grounded in SourceMind.

Use the existing SourceMind logo mark and deep navy/violet branding. Do not copy the
example product's name, product screenshots or marketing claims.

No new packages, backend APIs or authentication methods were added.

## Checks

From \`apps/web\` run:

\`\`\`bash
npm ci
npm run lint
npm test
npm run build
\`\`\`

Check manually: public homepage as signed-out user, all CTA links,
mobile navigation, sign-in to \`/workspace\`, direct protected links,
keyboard focus, FAQ expansion, and responsive product preview.
