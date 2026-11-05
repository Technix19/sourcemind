# SourceMind UI refresh (November 2026)

## Direction

A calm, light, document-first workspace rather than a decorative AI dashboard.

The interface uses a restrained indigo accent, neutral surfaces, subtle borders,
compact type, and data-dense lists. The stacked-source mark represents successive
pages or passages that are combined into an evidence-backed research result.

## Shared visual tokens

Defined in `apps/web/app/globals.css` using Tailwind v4 theme tokens:

| Role | Value |
| --- | --- |
| Background (`ink`) | `#f8fafc` |
| Panels (`panel`) | `#ffffff` |
| Subtle surface (`surface`) | `#f2f5fa` |
| Borders (`line`) | `#e2e7ef` |
| Primary text (`text`) | `#161d2d` |
| Muted text (`muted`) | `#627087` |
| Primary action (`lavender-deep`) | `#4f46e5` |
| Primary link (`lavender`) | `#4338ca` |
| Positive (`mint`) | `#087a57` |
| Warning (`amber`) | `#95580c` |
| Error (`danger`) | `#b42333` |

Reusable component classes: `sm-panel`, `sm-field`, `sm-primary`,
`sm-secondary`, `sm-page-title`, `sm-muted-label`.

## What changed

- Shared app shell, compact navigation, and consistent top status bar.
- SourceMind wordmark, layered-source vector mark, and favicon.
- Sign-in and sign-up form styling; AuthProvider and Supabase auth calls unchanged.
- Research workbench, smaller question composer, source shortcuts,
  citation presentation, and responsive evidence drawer.
- Searchable document list with real file metadata, statuses, Open and Remove actions.
- Evaluation report hierarchy: compact test metadata, prominent actual results,
  expandable methodology caveats, and consistent table styling.
- Source summary uses actual stored documents and no longer claims that uploaded data
  disappears on server restart.

## Intentional boundaries

The screenshots were references, not pixel-perfect specifications. **No fake
buttons, invented metrics, or unsupported features have been added**. For example,
the earlier concept mockup included feedback and "View details" controls; those
are not present because the application does not implement them yet.

The backend, schema, RLS, model prompts, storage, retrieval methods, API contracts,
and evaluation numbers are unchanged. The hosted Render free tier remains keyword-only,
even if local development supports meaning search.

## Review checklist

1. On the pull request run `npm ci`, `npm run lint`, `npm test`, and
   `npm run build` under `apps/web`.
2. On the resulting preview check login, create account, desktop navigation,
   mobile navigation, and keyboard focus.
3. Upload a PDF. Verify file metadata, Open, Remove/Cancel, and failure notices.
4. Ask a keyword question. Check generated/evidence-only/insufficient-evidence
   states, source links, source focus, and the responsive evidence drawer.
5. Visit Evaluation. Verify all real values and caveats remain accessible.
6. Check 375px, 768px, 1280px and widescreen widths.
7. Test `prefers-reduced-motion` and color contrast in a browser.

No production deployment is changed until the review pull request is merged.
