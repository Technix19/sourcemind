// Captures every screen, component and state of the SourceMind UI into a folder, plus an index.
// Usage: node ui-inventory.mjs <path to apps/api/.env> <output folder> <sample pdf>
import { chromium } from "playwright-core";
import os from "node:os";
import fs from "node:fs";
import path from "node:path";

const [ENV_PATH, OUT, PDF] = process.argv.slice(2);
const env = Object.fromEntries(
  fs.readFileSync(ENV_PATH, "utf8").split("\n").map((l) => l.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/)).filter(Boolean).map((m) => [m[1], m[2].trim()]),
);
const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const SB = (() => { const u = new URL(env.SUPABASE_URL); return `${u.protocol}//${u.host}`; })();
// Point CHROMIUM_PATH at a Chromium/Chrome executable (Playwright's bundled one works).
const exe = process.env.CHROMIUM_PATH ?? `${os.homedir()}/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell`;

const manifest = [];
const failed = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- helpers
async function apiToken() {
  const r = await fetch(`${SB}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: env.SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: env.SUPABASE_TEST_USER_A_EMAIL, password: env.SUPABASE_TEST_USER_A_PASSWORD }),
  });
  return (await r.json()).access_token;
}
async function cleanAccount() {
  const token = await apiToken();
  const h = { Authorization: `Bearer ${token}` };
  const docs = (await (await fetch(`${API}/api/v1/documents`, { headers: h })).json()).documents ?? [];
  for (const d of docs) await fetch(`${API}/api/v1/documents/${d.id}`, { method: "DELETE", headers: h });
  return docs.length;
}

// Hide the dev-only Next.js indicator and mask the signed-in email, so no image shows either.
async function prepare(page) {
  // Wait for the health check to settle, so images show the loaded state, not the brief 'Checking…' state.
  await page.waitForFunction(() => !/\bConnecting\b/.test(document.body.innerText), null, { timeout: 20000 }).catch(() => {});
  await sleep(150);
  await page.evaluate((email) => {
    document.querySelectorAll("nextjs-portal").forEach((n) => n.remove());
    const fake = "reviewer@example.com";
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.nodeValue.includes(email)) n.nodeValue = n.nodeValue.split(email).join(fake);
    document.querySelectorAll("[title],[aria-label]").forEach((el) => {
      for (const a of ["title", "aria-label"]) if ((el.getAttribute(a) || "").includes(email)) el.setAttribute(a, el.getAttribute(a).split(email).join(fake));
    });
  }, env.SUPABASE_TEST_USER_A_EMAIL);
}

function entry(folder, name, title, note) { manifest.push({ folder, file: `${name}.png`, title, note }); }

async function shotPage(page, folder, name, title, note, opts = {}) {
  try {
    fs.mkdirSync(path.join(OUT, folder), { recursive: true });
    await prepare(page);
    await page.screenshot({ path: path.join(OUT, folder, `${name}.png`), ...opts });
    entry(folder, name, title, note);
    console.log("ok   ", `${folder}/${name}`);
  } catch (e) { failed.push(`${folder}/${name}: ${e.message.split("\n")[0]}`); console.log("FAIL ", `${folder}/${name}`, e.message.split("\n")[0]); }
}
async function shotEl(page, locator, folder, name, title, note) {
  try {
    fs.mkdirSync(path.join(OUT, folder), { recursive: true });
    await locator.first().waitFor({ state: "visible", timeout: 8000 });
    await locator.first().scrollIntoViewIfNeeded();
    await prepare(page);
    await locator.first().screenshot({ path: path.join(OUT, folder, `${name}.png`) });
    entry(folder, name, title, note);
    console.log("ok   ", `${folder}/${name}`);
  } catch (e) { failed.push(`${folder}/${name}: ${e.message.split("\n")[0]}`); console.log("FAIL ", `${folder}/${name}`, e.message.split("\n")[0]); }
}
const ask = async (page, question) => {
  await page.locator("#question").fill(question);
  await page.getByRole("button", { name: /^Ask/ }).click();
};
const newConversation = async (page) => {
  const b = page.getByRole("button", { name: "New conversation" });
  if (await b.count()) await b.click();
  await sleep(300);
};

// ---------------------------------------------------------------- run
const browser = await chromium.launch({ executablePath: exe });
console.log("cleaned", await cleanAccount(), "leftover documents from the test account before starting");

// ===== Logged-out screens (fresh context, no session) =====
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/login`, { waitUntil: "networkidle" });
  await shotPage(page, "01-pages", "01-login-sign-in", "Sign in", "/login, default mode");
  await shotEl(page, page.locator("form").first(), "02-components", "login-form", "Sign-in form", "Email, password, submit, switch to create account");
  await page.getByRole("button", { name: "Create an account" }).click();
  await sleep(300);
  await shotPage(page, "01-pages", "02-login-create-account", "Create account", "/login after choosing Create an account (adds the 8-character hint)");
  await page.getByRole("button", { name: /Sign in/ }).last().click().catch(() => {});
  await sleep(300);
  await page.getByLabel("Email").fill("reviewer@example.com");
  await page.getByLabel("Password").fill("not-the-password-1");
  await page.getByRole("button", { name: "Sign in" }).first().click();
  await page.getByText("Incorrect email or password.").waitFor({ timeout: 20000 }).catch(() => {});
  await shotPage(page, "03-states", "login-wrong-password", "Sign-in error", "Wrong email or password (a made-up address is shown, not a real one)");
  await ctx.close();

  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
  const mpage = await mctx.newPage();
  await mpage.goto(`${WEB}/login`, { waitUntil: "networkidle" });
  await shotPage(mpage, "04-mobile-390", "login", "Sign in (phone)", "390 x 844");
  await mctx.close();
}

// ===== Signed-in screens =====
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
const page = await ctx.newPage();
await page.goto(`${WEB}/login`, { waitUntil: "networkidle" });
await page.getByLabel("Email").fill(env.SUPABASE_TEST_USER_A_EMAIL);
await page.getByLabel("Password").fill(env.SUPABASE_TEST_USER_A_PASSWORD);
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(`${WEB}/`, { timeout: 60000 });
await page.getByRole("heading", { name: "Ask your documents" }).waitFor({ timeout: 30000 });

// -- empty library
await shotPage(page, "01-pages", "03-ask-start-no-documents", "Ask questions: first run", "/ with an empty library: hero, upload zone, starter questions, evidence panel and source health");
await shotEl(page, page.locator('aside:has(nav[aria-label="Main"])'), "02-components", "sidebar", "Sidebar", "Brand, workspace, navigation, signed-in status, sign out (email masked)");
await shotEl(page, page.locator("header").first(), "02-components", "topbar", "Top bar", "Breadcrumb, answer-mode status, sign out, compact nav on small screens");
await shotEl(page, page.locator("div.border-dashed").first(), "02-components", "upload-zone", "Upload zone", "Drop area with browse link, accepted types and size limit");
await shotEl(page, page.getByText("Try asking").locator(".."), "02-components", "quick-start", "Starter questions", "Three prompts that fill the question box");
await shotEl(page, page.getByRole("region", { name: "Your sources" }), "02-components", "sources-panel-empty", "Sources panel: empty", "Right-hand panel before any document is uploaded");
await shotEl(page, page.locator("form").filter({ has: page.locator("#question") }), "02-components", "question-form-no-documents", "Question form: no documents", "Disabled input with a link to upload");

// keyboard focus: skip link and the first tab stop
await page.goto(`${WEB}/`, { waitUntil: "networkidle" });
await page.keyboard.press("Tab");
await sleep(200);
await shotPage(page, "03-states", "skip-link-focused", "Skip link (keyboard focus)", "First Tab stop: the 'Skip to main content' link becomes visible", { clip: { x: 0, y: 0, width: 520, height: 140 } });

// API offline banner
await page.route("**/api/v1/documents", (r) => r.abort());
await page.goto(`${WEB}/`, { waitUntil: "domcontentloaded" });
await page.getByRole("button", { name: "Retry" }).waitFor({ timeout: 25000 }).catch(() => {});
await sleep(800);
await shotPage(page, "03-states", "api-offline-banner", "API offline banner", "What the app shows when the API cannot be reached (request blocked on purpose)");
await page.unroute("**/api/v1/documents");

// documents page, empty
await page.goto(`${WEB}/documents`, { waitUntil: "networkidle" });
await shotPage(page, "01-pages", "04-documents-empty", "Documents: empty library", "/documents with no files");

// -- upload the sample document through the real UI
await page.locator('input[type="file"]').first().setInputFiles(PDF);
await page.getByText("adaptive-practice-brief.pdf").first().waitFor({ timeout: 120000 });
await page.waitForFunction(() => !document.body.innerText.includes("Uploading and indexing"), null, { timeout: 120000 }).catch(() => {});
await sleep(1500);
await shotPage(page, "01-pages", "05-documents-with-document", "Documents: one file", "/documents after uploading the sample PDF");
await shotEl(page, page.locator("li").filter({ hasText: "adaptive-practice-brief.pdf" }), "02-components", "document-list-item", "Document row", "Type badge, name, size, pages, passages, status, Open, Remove");
await shotEl(page, page.locator("h1.sm-page-title").locator("xpath=../.."), "02-components", "documents-header", "Documents header", "Title, counts, upload button");
await shotEl(page, page.getByPlaceholder("Search documents by name…"), "02-components", "documents-search", "Documents search box", "Filter by file name");
await page.getByRole("button", { name: /^Remove/ }).first().click();
await sleep(300);
await shotEl(page, page.locator("li").filter({ hasText: "adaptive-practice-brief.pdf" }), "03-states", "document-remove-confirm", "Remove confirmation", "Inline Confirm / Cancel after clicking Remove");
await page.getByRole("button", { name: "Cancel" }).first().click();

// -- ask page with a document
await page.goto(`${WEB}/`, { waitUntil: "networkidle" });
await page.getByText("Try asking").waitFor({ timeout: 30000 });
await shotPage(page, "01-pages", "06-ask-start-with-document", "Ask questions: ready", "/ with one document indexed");
await shotEl(page, page.getByRole("region", { name: "Your sources" }), "02-components", "sources-panel-with-document", "Sources panel: one document", "Lists each indexed file with its pages and passages");
await shotEl(page, page.getByText("Try asking").locator(".."), "02-components", "quick-start-with-documents", "Starter chips", "Same chips once a document exists");
await page.getByRole("button", { name: /Identify limitations/ }).click();
await sleep(300);
await shotEl(page, page.locator("form").filter({ has: page.locator("#question") }), "02-components", "question-form-ready", "Question form: filled", "Starter question inserted; Search-by choice and Generate option shown");
await shotPage(page, "03-states", "quick-start-filled", "Starter question picked", "Picking a starter fills the box but does not send it");

// keyword answer (with a deliberate delay so the pending state can be captured)
await page.route("**/api/v1/queries", async (route) => { await sleep(2500); await route.continue(); });
await page.getByRole("button", { name: /^Ask/ }).click();
await sleep(900);
await shotPage(page, "03-states", "ask-pending", "Searching…", "Shown while the API is working (the delay was added for this capture)");
await page.getByText(/Keyword search|Meaning search/).first().waitFor({ timeout: 30000 });
await page.unroute("**/api/v1/queries");
await sleep(800);
await shotPage(page, "01-pages", "07-ask-answer-keyword", "Answer: keyword search", "Evidence-only answer with the supporting passages in the right rail");
await shotEl(page, page.locator("div.space-y-6 > div").first(), "02-components", "conversation-turn", "Conversation turn", "The question bubble and SourceMind's reply card with its badge");
await shotEl(page, page.getByRole("region", { name: "Supporting source passages" }), "02-components", "evidence-panel", "Evidence panel", "Ranked passages with page numbers and match scores");
await shotEl(page, page.locator('[aria-label^="Source 1:"]'), "02-components", "evidence-card", "Evidence card", "One passage: citation number, file, page, rank, score, excerpt, Open page");

// meaning search
await newConversation(page);
await page.getByLabel("Meaning").check().catch(() => {});
await ask(page, "Which inputs does the model use?");
await page.getByText("Meaning search").first().waitFor({ timeout: 60000 }).catch(() => {});
await sleep(800);
await shotPage(page, "01-pages", "08-ask-answer-meaning", "Answer: meaning search", "Same app, Meaning selected (finds passages that share no words with the question)");

// generated answer with citations
await newConversation(page);
await page.getByLabel("Keyword").check().catch(() => {});
await page.getByLabel(/Generate an answer/).check().catch(() => {});
await ask(page, "What are the limitations of the study?");
await page.getByText(/Generated by/).first().waitFor({ timeout: 90000 }).catch(() => {});
await sleep(800);
await shotPage(page, "01-pages", "09-ask-answer-generated", "Answer: generated with citations", "Claude's answer with [n] citation chips and the model label");
await shotEl(page, page.locator("[aria-busy]").first(), "02-components", "answer-card-generated", "Generated answer card", "Answer text with citation chips, 'Generated by' line");
const chip = page.locator('[aria-label^="Show source"]').first();
if (await chip.count()) { await chip.click(); await sleep(500); await shotPage(page, "03-states", "citation-selected", "Citation chip activated", "Clicking [n] highlights the matching evidence card"); }

// not enough evidence
await newConversation(page);
await page.getByLabel(/Generate an answer/).uncheck().catch(() => {});
await ask(page, "galaxies and nebulae");
await page.getByText(/couldn't find enough evidence/).first().waitFor({ timeout: 30000 }).catch(() => {});
await sleep(500);
await shotPage(page, "01-pages", "10-ask-insufficient-evidence", "Answer: not enough evidence", "The product declines instead of guessing");
await shotEl(page, page.locator("div.space-y-6 > div").first(), "02-components", "conversation-turn-insufficient", "Turn: not enough evidence", "Abstention reply");

// -- evaluation
await page.goto(`${WEB}/documents`, { waitUntil: "domcontentloaded" });
await page.route("**/api/v1/evaluation/latest", async (route) => { await sleep(2500); await route.continue(); });
await page.getByRole("link", { name: /Evaluation/ }).first().click();
await sleep(900);
await shotPage(page, "03-states", "evaluation-loading", "Evaluation: loading", "Shown while the results download (delay added for this capture)");
await page.getByText("Read this first").first().waitFor({ timeout: 60000 });
await page.unroute("**/api/v1/evaluation/latest");
await sleep(600);
await shotPage(page, "01-pages", "11-evaluation-top", "Evaluation: top of page", "Heading, run details and the 'Read this first' caveats");
await shotPage(page, "01-pages", "12-evaluation-full-page", "Evaluation: full page", "Every section on one tall image", { fullPage: true });
await shotEl(page, page.locator('aside[aria-labelledby="read-first"]'), "02-components", "eval-caveats", "Evaluation caveats box", "The limits that come before the numbers");
const sections = page.locator("main section");
for (let i = 0; i < (await sections.count()); i++) {
  const title = (await sections.nth(i).locator("h2").first().innerText()).trim();
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  await shotEl(page, sections.nth(i), "02-components", `eval-section-${String(i + 1).padStart(2, "0")}-${slug}`, `Evaluation section: ${title}`, "One section of the results page");
}
const tables = page.locator("main table");
for (let i = 0; i < (await tables.count()); i++) {
  const cap = (await tables.nth(i).locator("caption").innerText().catch(() => `table ${i + 1}`)).trim();
  const slug = cap.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48);
  await shotEl(page, tables.nth(i), "02-components", `eval-table-${String(i + 1).padStart(2, "0")}-${slug}`, `Table: ${cap}`, "Result table (bars are decorative; numbers are written out)");
}

// ===== Responsive: phone (390) and tablet (820) =====
for (const [label, folder, size] of [["phone", "04-mobile-390", { width: 390, height: 844 }], ["tablet", "05-tablet-820", { width: 820, height: 1180 }]]) {
  await page.setViewportSize(size);
  await page.goto(`${WEB}/`, { waitUntil: "networkidle" });
  await page.getByText("Try asking").waitFor({ timeout: 30000 });
  await shotPage(page, folder, "ask-start", `Ask questions: ready (${label})`, `${size.width} x ${size.height}`);
  await shotEl(page, page.locator('nav[aria-label="Main (compact)"]'), folder, "compact-navigation", `Compact navigation (${label})`, "Navigation moves from the sidebar into the top bar below the large breakpoint");
  await ask(page, "What are the limitations of the study?");
  await page.getByText(/Keyword search|Meaning search/).first().waitFor({ timeout: 60000 });
  await sleep(700);
  await shotPage(page, folder, "ask-answer", `Answer (${label})`, "Evidence moves into a drawer on small screens");
  const sources = page.getByRole("button", { name: /^Sources \(/ }).first();
  if (await sources.isVisible().catch(() => false)) {
    await sources.click();
    await sleep(600);
    await shotPage(page, folder, "sources-drawer-open", `Sources drawer (${label})`, "Bottom sheet with the evidence cards");
    await page.getByRole("button", { name: "Close" }).first().click();
    await sleep(300);
  }
  await page.goto(`${WEB}/documents`, { waitUntil: "networkidle" });
  await shotPage(page, folder, "documents", `Documents (${label})`, "File row wraps its actions on narrow screens");
  await page.goto(`${WEB}/evaluation`, { waitUntil: "networkidle" });
  await page.getByText("Read this first").first().waitFor({ timeout: 60000 });
  await shotPage(page, folder, "evaluation-top", `Evaluation (${label})`, "Caveats first; tables scroll sideways inside their own box");
}

// ===== Dark theme (the redesign added a switcher; the default follows the system, captured above in light) =====
await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(`${WEB}/`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Switch to dark mode" }).first().click();
await sleep(500);
await shotEl(page, page.locator("header").first(), "06-dark-theme", "topbar-dark", "Top bar in dark theme", "Theme switcher now shows the sun icon");
await shotPage(page, "06-dark-theme", "ask-start", "Ask questions: ready (dark)", "/ with one document indexed");
await ask(page, "What are the limitations of the study?");
await page.getByText(/Keyword search|Meaning search/).first().waitFor({ timeout: 60000 });
await sleep(700);
await shotPage(page, "06-dark-theme", "ask-answer", "Answer (dark)", "Evidence-only answer");
await page.goto(`${WEB}/documents`, { waitUntil: "networkidle" });
await shotPage(page, "06-dark-theme", "documents", "Documents (dark)", "/documents with one file");
await page.goto(`${WEB}/evaluation`, { waitUntil: "networkidle" });
await page.getByText("Read this first").first().waitFor({ timeout: 60000 });
await shotPage(page, "06-dark-theme", "evaluation-top", "Evaluation (dark)", "Caveats and ranking table");
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${WEB}/`, { waitUntil: "networkidle" });
await shotPage(page, "06-dark-theme", "mobile-ask", "Ask questions (phone, dark)", "390 x 844");

await browser.close();
console.log("cleaned up", await cleanAccount(), "test document(s) from the test account");

// ---------------------------------------------------------------- index
const groups = {
  "01-pages": "Full pages (desktop, 1440 x 900)", "02-components": "Individual components and sections",
  "03-states": "Loading, error, focus and interaction states", "04-mobile-390": "Phone layout (390 x 844)", "05-tablet-820": "Tablet layout (820 x 1180)", "06-dark-theme": "Dark theme",
};
let md = `# SourceMind UI inventory\n\nCaptured ${new Date().toISOString().slice(0, 10)} from the local app (all features on: keyword and meaning search, generated answers) with the synthetic sample document \`data/sample/adaptive-practice-brief.pdf\`. The signed-in email is masked as \`reviewer@example.com\`. The dev-only Next.js indicator is removed from every image. Regenerate with `capture/ui-inventory.mjs` (see `capture/README.md`). Problems noticed while capturing are in [OBSERVATIONS.md](OBSERVATIONS.md).\n\n`;
for (const [folder, heading] of Object.entries(groups)) {
  const rows = manifest.filter((m) => m.folder === folder);
  if (!rows.length) continue;
  md += `## ${heading}\n\nFolder: \`${folder}/\`\n\n| File | What it shows | Notes |\n|---|---|---|\n`;
  for (const r of rows) md += `| [${r.file}](${folder}/${r.file}) | ${r.title} | ${r.note} |\n`;
  md += "\n";
}
if (failed.length) md += `## Not captured\n\n${failed.map((f) => `- ${f}`).join("\n")}\n\n`;
fs.writeFileSync(path.join(OUT, "INDEX.md"), md);
fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify({ captured: manifest, failed }, null, 1));
console.log(`\n${manifest.length} captured, ${failed.length} failed`);
