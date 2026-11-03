"use client";

const PROMPTS = [
  { title: "Summarize the main idea", question: "What is the main idea of this document?" },
  { title: "Find key findings", question: "What are the key findings?" },
  { title: "Identify limitations", question: "What limitations are mentioned?" },
];

/** Fills the question box; it never sends anything by itself. */
export function QuickStart({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div>
      <p className="mb-3 text-xs font-bold tracking-wider text-muted">GET STARTED WITH A QUESTION</p>
      <ul className="grid gap-3 sm:grid-cols-3">
        {PROMPTS.map((p) => (
          <li key={p.title}>
            <button
              type="button"
              onClick={() => onPick(p.question)}
              className="h-full w-full rounded-xl border border-line bg-panel p-4 text-left transition-colors hover:border-lavender/60"
            >
              <span className="block font-bold">{p.title}</span>
              <span className="mt-1 block text-sm text-muted">{p.question}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
