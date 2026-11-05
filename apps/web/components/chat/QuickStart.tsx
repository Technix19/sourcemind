"use client";

import { UiIcon } from "@/components/ui/UiIcon";

const PROMPTS = [
  { title: "Summarize the main idea", question: "What is the main idea of this document?" },
  { title: "Find key findings", question: "What are the key findings?" },
  { title: "Identify limitations", question: "What limitations are mentioned?" },
];

/** Fills the question box; it never sends anything by itself. */
export function QuickStart({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div>
      <p className="mb-3 text-[13px] font-bold text-text">Try asking</p>
      <ul className="flex flex-wrap gap-2">
        {PROMPTS.map((prompt) => (
          <li key={prompt.title}>
            <button
              type="button"
              onClick={() => onPick(prompt.question)}
              className="sm-secondary group text-left"
              title={prompt.question}
            >
              {prompt.title}
              <UiIcon name="arrow" size={14} className="text-[#8a96ac] dark:text-[#a9aac4] group-hover:text-lavender" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
