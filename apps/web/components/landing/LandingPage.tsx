import Link from "next/link";
import { BrandMark } from "@/components/ui/BrandLogo";
import { UiIcon, type IconName } from "@/components/ui/UiIcon";

const buttonPrimary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#855cf0] px-5 py-3 text-[13px] font-bold text-white transition-colors hover:bg-[#966ff5] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#bea2ff]";

const buttonOutline =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#47455e] bg-[#1a1929] px-5 py-3 text-[13px] font-semibold text-[#ece8fa] transition-colors hover:border-[#8c79b8] hover:bg-[#242237] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#bea2ff]";

function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <BrandMark size={compact ? 28 : 34} />
      <span className={"font-black tracking-[-.04em] text-white " + (compact ? "text-[17px]" : "text-[20px]")}>
        SourceMind
      </span>
    </span>
  );
}

function SampleWorkspace() {
  return (
    <div aria-label="Illustrative SourceMind workspace showing a sourced answer and supporting passage" className="relative mx-auto max-w-[1120px]">
      <div className="absolute -inset-x-6 -bottom-7 -top-6 rounded-[28px] bg-[#8560da]/[0.055] blur-[50px]" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-[13px] border border-[#424058] bg-[#161622] shadow-[0_35px_100px_rgba(0,0,0,0.45)]">
        <div className="flex h-10 items-center justify-between border-b border-[#333248] bg-[#1b1a29] px-4 text-[11px] text-[#a29fb7]">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            <span className="size-2 rounded-full bg-[#6b506e]" />
            <span className="size-2 rounded-full bg-[#63516f]" />
            <span className="size-2 rounded-full bg-[#4f5576]" />
          </div>
          <span>Research workspace</span>
          <span className="hidden items-center gap-1.5 sm:inline-flex"><span className="size-1.5 rounded-full bg-[#68d9b0]" /> Evidence available</span>
        </div>
        <div className="grid min-h-[340px] grid-cols-[minmax(0,1fr)] md:grid-cols-[175px_minmax(0,1fr)] lg:grid-cols-[182px_minmax(0,1fr)_280px]">
          <aside className="hidden border-r border-[#343247] bg-[#181725] p-5 md:block">
            <Wordmark compact />
            <p className="mt-9 text-[10px] font-bold text-[#9390a8]">WORKSPACE</p>
            <div className="mt-2 rounded-md border border-[#3a384e] px-2.5 py-2.5 text-left text-[11px] text-[#dedbeb]">
              <UiIcon name="folder" size={13} className="mr-1.5 inline align-middle text-[#b99cf5]" />
              Research workspace
            </div>
            <p className="mt-7 text-[10px] font-bold text-[#9390a8]">NAVIGATION</p>
            <div className="mt-3 space-y-1 text-[11px]">
              <p className="flex items-center gap-2 rounded-md bg-[#332749] px-2.5 py-2.5 font-semibold text-[#d9c6ff]"><UiIcon name="message" size={14} /> Ask questions</p>
              <p className="flex items-center gap-2 px-2.5 py-2.5 text-[#a3a1b6]"><UiIcon name="file" size={14} /> Documents</p>
              <p className="flex items-center gap-2 px-2.5 py-2.5 text-[#a3a1b6]"><UiIcon name="chart" size={14} /> Evaluation</p>
            </div>
          </aside>

          <div className="min-w-0 px-5 py-6 sm:px-7 sm:py-8">
            <div className="mb-5">
              <p className="text-left text-[10px] font-medium text-[#a49ebc]">Workspace / Ask questions</p>
              <h3 className="mt-1.5 text-left text-[22px] font-bold tracking-[-.04em] text-white sm:text-[25px]">Ask your documents</h3>
              <p className="mt-1 text-left text-[11px] leading-5 text-[#a5a2b8]">Ask a question and review the original passages.</p>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-[#49405f] bg-[#222133] px-3 py-3 text-left">
              <span className="min-w-0 flex-1 truncate text-[12px] text-[#eeeaf9]">What are the limitations of the study?</span>
              <span className="flex shrink-0 items-center rounded-md bg-[#7951de] px-2.5 py-1.5 text-[10px] font-bold text-white">Ask <UiIcon name="arrow" size={12} className="ml-1" /></span>
            </div>
            <div className="mt-4 rounded-lg border border-[#454058] bg-[#1c1b2a] p-4 text-left sm:p-5">
              <div className="flex items-center justify-between gap-2 border-b border-[#373449] pb-3">
                <span className="text-[11px] font-bold text-[#f4f0ff]">SourceMind</span>
                <span className="rounded bg-[#1e3b35] px-2 py-1 text-[10px] font-semibold text-[#8deac8]">Grounded</span>
              </div>
              <p className="mt-3 text-[12px] leading-[1.85] text-[#dfdcea]">
                The example study describes a <strong className="font-semibold text-white">small, synthetic dataset</strong> and notes that its findings should not be generalized beyond the demonstration.
                <span className="ml-1 rounded bg-[#40305c] px-1.5 py-0.5 text-[10px] text-[#dbc5ff]">[1]</span>
              </p>
              <p className="mt-3 text-[10px] text-[#a29fb6]">Answer based on retrieved document excerpts.</p>
            </div>
          </div>

          <aside className="hidden border-l border-[#343247] bg-[#1a1928] px-4 py-8 lg:block">
            <div className="flex items-center justify-between">
              <h4 className="text-[13px] font-bold text-white">Evidence &amp; sources</h4>
              <span className="rounded bg-[#2d2a40] px-2 py-1 text-[10px] text-[#d0c7e7]">1</span>
            </div>
            <p className="mt-2 text-left text-[11px] leading-5 text-[#a6a2bb]">Supporting passages for this answer.</p>
            <div className="mt-4 rounded-lg border border-[#454058] bg-[#222033] p-3 text-left">
              <p className="truncate text-[11px] font-bold text-white">adaptive-practice-brief.pdf</p>
              <p className="mt-2 text-[10px] text-[#beb8d0]">Page 3 · Source 1</p>
              <p className="mt-3 text-[11px] leading-[1.7] text-[#d5d0e2]">
                “The synthetic dataset is small and does not represent real learners, so the results should not be generalised.”
              </p>
              <p className="mt-3 text-[11px] font-semibold text-[#c7acff]">Open original page</p>
            </div>
          </aside>
        </div>
      </div>
      <p className="mt-4 text-center text-[11px] text-[#89879d]">Illustrative interface preview using an example document. Actual results depend on your sources.</p>
    </div>
  );
}

const features: { icon: IconName; title: string; description: string }[] = [
  {
    icon: "file",
    title: "Your documents, organized",
    description: "Upload text-based PDFs, TXT, or Markdown files to a private workspace. Keep your research material together.",
  },
  {
    icon: "search",
    title: "Search for the right passage",
    description: "Find relevant excerpts with keyword retrieval. Meaning-based search is supported where enabled.",
  },
  {
    icon: "layers",
    title: "Evidence beside the answer",
    description: "Inspect the underlying passage and its page number instead of taking every answer on faith.",
  },
  {
    icon: "message",
    title: "Answers when you need them",
    description: "Choose retrieved evidence alone or optional AI-generated answers when generation is available.",
  },
  {
    icon: "folder",
    title: "A workspace for your files",
    description: "Documents and source text are stored per signed-in user, with database access controls.",
  },
  {
    icon: "chart",
    title: "Evaluation in the open",
    description: "Explore how retrieval methods performed in a documented, small-scale test and review their limitations.",
  },
];

const steps = [
  { number: "01", title: "Add your sources", text: "Bring in a text-based PDF, TXT, or Markdown file. SourceMind extracts passages you can search." },
  { number: "02", title: "Ask what matters", text: "Search the material with your own question. Generate an answer when that option is available." },
  { number: "03", title: "Go back to the source", text: "Read the cited passage and open its original page before relying on an answer." },
];

const questions = [
  { question: "What files can I upload?", answer: "SourceMind supports text-based PDF, TXT, and Markdown files. Image-only or scanned PDFs require OCR first; OCR is not currently built in." },
  { question: "Does SourceMind always generate an AI answer?", answer: "No. You can use it to retrieve supporting passages without generating an answer. AI generation is optional and depends on whether the server has the feature enabled." },
  { question: "Can I check where an answer came from?", answer: "Yes. Retrieved evidence includes document names and page references. When the original PDF is stored, you can open the referenced page." },
  { question: "Are uploaded documents private?", answer: "Documents belong to your signed-in workspace. SourceMind uses Supabase authentication, row-level security, and private file storage. If you choose AI-generated answers, the question and relevant excerpts are sent to the model provider." },
  { question: "What if the document does not contain the answer?", answer: "SourceMind can indicate that there is not enough relevant evidence rather than presenting an unsupported answer. As with any AI-assisted research tool, verify important details against the original sources." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0e0e19] font-sans text-[#f4f2fb]">
      <header className="relative z-20 border-b border-[#292838] bg-[#0e0e19]/95">
        <div className="mx-auto flex min-h-[76px] max-w-[1180px] items-center justify-between gap-5 px-5 sm:px-8">
          <Link href="/" aria-label="SourceMind home" className="rounded-lg"><Wordmark /></Link>
          <nav aria-label="Landing page" className="hidden items-center gap-8 text-[13px] font-medium text-[#afabbe] md:flex">
            <a href="#how-it-works" className="rounded hover:text-white">How it works</a>
            <a href="#features" className="rounded hover:text-white">Features</a>
            <a href="#faq" className="rounded hover:text-white">FAQ</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="hidden rounded px-2 py-2 text-[13px] font-semibold text-[#d4cedf] hover:text-white sm:inline">Sign in</Link>
            <Link href="/workspace" className={buttonPrimary}>Open workspace <UiIcon name="arrow" size={15} /></Link>
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="outline-none">
        <section className="relative overflow-hidden px-5 pt-20 pb-14 text-center sm:px-8 sm:pt-28">
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-[650px] max-w-[1150px] bg-[radial-gradient(ellipse_at_50%_35%,rgba(111,79,176,0.17),transparent_65%)]" />
          <div className="relative mx-auto max-w-[850px]">
            <p className="mb-5 text-[12px] font-semibold text-[#bbb0df]">Research your documents with evidence, not guesses.</p>
            <h1 className="text-balance text-[43px] font-black leading-[1.08] tracking-[-.055em] text-white sm:text-[63px] lg:text-[75px]">
              Ask your documents.<br />Check the evidence.
            </h1>
            <p className="mx-auto mt-6 max-w-[590px] text-pretty text-[15px] leading-[1.85] text-[#b6b2c5] sm:text-[17px]">
              Turn your PDFs and notes into a searchable research workspace. Find useful passages, get optional AI answers, and trace the details back to their source.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/workspace" className={buttonPrimary}>Start researching <UiIcon name="arrow" size={16} /></Link>
              <a href="#how-it-works" className={buttonOutline}>See how it works</a>
            </div>
            <p className="mt-4 text-[12px] text-[#8f8b9e]">Sign in to create your private research workspace.</p>
          </div>
        </section>

        <section aria-label="Product preview" className="relative mx-auto max-w-[1230px] px-5 pb-24 sm:px-8 sm:pb-28">
          <SampleWorkspace />
        </section>

        <section id="how-it-works" className="scroll-mt-20 border-t border-[#272638] bg-[#12121f] px-5 py-23 sm:px-8">
          <div className="mx-auto max-w-[1110px] py-20">
            <div className="max-w-[610px]">
              <h2 className="text-[32px] font-black tracking-[-.04em] text-white sm:text-[42px]">From file to finding.</h2>
              <p className="mt-3 text-[15px] leading-7 text-[#b3afc1]">A straightforward workflow designed to keep the original document in view.</p>
            </div>
            <div className="mt-11 grid border-t border-[#39374b] md:grid-cols-3">
              {steps.map((step) => (
                <div key={step.number} className="border-b border-[#39374b] py-7 md:border-b-0 md:pr-9 md:[&:not(:first-child)]:border-l md:[&:not(:first-child)]:pl-9">
                  <span className="text-[12px] font-bold text-[#b6a0ef]">{step.number}</span>
                  <h3 className="mt-4 text-[18px] font-bold text-[#f6f3fe]">{step.title}</h3>
                  <p className="mt-3 text-[13px] leading-[1.8] text-[#aaa6bb]">{step.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="scroll-mt-20 px-5 py-20 sm:px-8 sm:py-24">
          <div className="mx-auto max-w-[1110px]">
            <div className="mx-auto max-w-[700px] text-center">
              <h2 className="text-[32px] font-black tracking-[-.04em] text-white sm:text-[42px]">Built for answers you can verify.</h2>
              <p className="mt-3 text-[15px] leading-7 text-[#b3afc1]">Useful research tools, without making the evidence an afterthought.</p>
            </div>
            <div className="mt-13 grid overflow-hidden rounded-xl border border-[#39374a] md:grid-cols-2 lg:grid-cols-3">
              {features.map((feature, index) => (
                <div key={feature.title} className={"min-w-0 p-7 sm:p-8 " +
                  "border-b border-[#39374a] " +
                  (index % 2 === 0 ? "md:border-r lg:border-r-0 " : "") +
                  (index % 3 !== 2 ? "lg:border-r " : "") +
                  (index >= 3 ? "lg:border-b-0 " : "") +
                  (index >= 4 ? "md:border-b-0 " : "")
                }>
                  <UiIcon name={feature.icon} size={21} className="text-[#b4a0ee]" />
                  <h3 className="mt-5 text-[16px] font-bold text-white">{feature.title}</h3>
                  <p className="mt-3 text-[13px] leading-[1.85] text-[#aaa6bb]">{feature.description}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-center text-[12px] leading-6 text-[#858196]">Available features may vary with server configuration. The hosted demo may not support meaning-based search.</p>
          </div>
        </section>

        <section className="border-y border-[#2b293b] bg-[#141320] px-5 py-18 sm:px-8">
          <div className="mx-auto flex max-w-[1090px] flex-col gap-7 py-12 md:flex-row md:items-center md:justify-between">
            <div className="max-w-[610px]">
              <h2 className="text-[27px] font-black tracking-[-.035em] text-white sm:text-[33px]">A better answer starts with a better source.</h2>
              <p className="mt-3 text-[14px] leading-7 text-[#b2aec1]">SourceMind was designed around the question that matters after every AI response: where did that come from?</p>
            </div>
            <Link href="/workspace" className={buttonPrimary}>Open SourceMind <UiIcon name="arrow" size={16} /></Link>
          </div>
        </section>

        <section id="faq" className="scroll-mt-20 px-5 py-22 sm:px-8 sm:py-28">
          <div className="mx-auto max-w-[810px] py-20">
            <h2 className="text-center text-[32px] font-black tracking-[-.04em] text-white sm:text-[42px]">Frequently asked questions</h2>
            <p className="mt-3 text-center text-[14px] leading-7 text-[#a9a5b9]">A few things worth knowing before you start.</p>
            <div className="mt-10 divide-y divide-[#383648] border-y border-[#383648]">
              {questions.map((item) => (
                <details key={item.question} className="group py-1">
                  <summary className="flex min-h-[60px] cursor-pointer list-none items-center justify-between gap-4 rounded px-1 text-left text-[14px] font-semibold text-[#f1eef7] marker:hidden hover:text-[#d0beff] [&::-webkit-details-marker]:hidden">
                    {item.question}
                    <UiIcon name="plus" size={17} className="shrink-0 text-[#b3a1df] transition-transform group-open:rotate-45" />
                  </summary>
                  <p className="max-w-[680px] px-1 pb-6 text-[13px] leading-[1.9] text-[#aca8bd]">{item.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#302e40] bg-[#0b0b14] px-5 py-10 sm:px-8">
        <div className="mx-auto flex max-w-[1110px] flex-col justify-between gap-7 sm:flex-row sm:items-center">
          <div>
            <Link href="/" aria-label="SourceMind home"><Wordmark compact /></Link>
            <p className="mt-3 text-[12px] text-[#aaa6ba]">Document research, grounded in evidence.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[12px] font-medium text-[#b4afc1]">
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#faq" className="hover:text-white">FAQ</a>
            <Link href="/workspace" className="hover:text-white">Workspace</Link>
            <a href="https://github.com/Technix19/sourcemind" target="_blank" rel="noopener noreferrer" className="hover:text-white">GitHub</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
