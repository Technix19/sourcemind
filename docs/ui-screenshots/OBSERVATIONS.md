# Problems noticed while capturing the UI

Checked 2026-11-05 against the UI **after** the redesign and dark mode were merged (an earlier pass on the old UI found six
problems; this is their status). I looked at about fifteen of the 69 images one by one (home, sidebar, generated answer,
dark theme, skip-link focus, phone drawer, offline banner and the error and loading states in both passes) and read the
code behind each finding; the rest were produced by the same script and not inspected image by image.

| # | Problem | Status after the redesign | Evidence |
|---|---|---|---|
| 1 | False text: "Your data stays in memory... not saved to a database in this local prototype" | **Fixed.** The panel is now a "Sources" list; the text no longer exists in the code. | `02-components/sources-panel-empty.png` |
| 2 | **Generated answers show raw Markdown:** literal `**bold**` and `- ` bullets, and a stray space before the full stop after a citation chip ("learners [1] .") | **Still present.** | `01-pages/09-ask-answer-generated.png`, `02-components/answer-card-generated.png` |
| 3 | Status said a red "API offline" while still loading | **Fixed.** It now says "Connecting", then "Connected"; "API offline" appears only on a real failure. | `03-states/api-offline-banner.png` vs `01-pages/03-ask-start-no-documents.png` |
| 4 | The focused skip link overlaps the brand logo | **Still present.** | `03-states/skip-link-focused.png` |
| 5 | With no documents the question form still shows "Search by" and "Generate an answer" next to a disabled input | **Still present.** | `02-components/question-form-no-documents.png` |
| 6 | **"Grounded" badge on a reply that says it found nothing.** A reply that opens with "I couldn't find that information..." and then explains is treated as a normal generated answer, so it gets the green "Grounded" badge. Found by reading the answers in the generation evaluation (`docs/m8-generation-eval.md`, section 5); not visible in these images. | **Still present.** `badgeFor` is unchanged and `is_abstention` in `app/answering.py` is still an exact match. | code only |

## New things seen in the redesigned UI
- The home page repeats the document and passage counts twice (top-right chip and the Sources panel). Minor.
- A "Documents" shortcut button sits in the top bar on every page, including the Documents page itself.
- Dark theme works on every page captured; the theme switch icon changes to the sun. No contrast problem was visible in the dark images I looked at, but contrast was not measured.
- Light is the default in the captures only because the browser is pinned to light; the app itself follows the system setting.

## Suggested order
1. #2 (visible on every generated answer; either tell the model to write plain sentences or render a small safe subset such as bold and lists, never raw HTML).
2. #6 (a correctness-of-signal bug; needs a product decision, see the evaluation doc).
3. #4 and #5 (small polish).
