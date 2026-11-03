"use client";

import { splitCitations } from "@/lib/citations";
import type { Evidence } from "@/lib/types";

/**
 * Renders an answer as plain text with [n] markers turned into buttons.
 * Everything is rendered as React text (never as HTML), so a malicious
 * document or model reply cannot inject markup.
 */
export function AnswerText({
  text,
  evidence,
  onCite,
}: {
  text: string;
  evidence: Evidence[];
  onCite: (citationId: string) => void;
}) {
  const byId = new Map(evidence.map((e) => [e.citation_id, e]));
  return (
    <div className="space-y-3 leading-relaxed">
      {text.split(/\n{2,}/).map((paragraph, p) => (
        <p key={p} className="whitespace-pre-wrap">
          {splitCitations(paragraph).map((segment, i) => {
            if (segment.type === "text") return segment.text;
            return (
              <span key={i} className="whitespace-nowrap">
                {segment.numbers.map((n, j) => {
                  const source = byId.get(n);
                  // A marker with no matching evidence stays as inert text. The API strips
                  // these already; this is defence in depth, not a link to nowhere.
                  if (!source) return <span key={j}>[{n}]</span>;
                  return (
                    <button
                      key={j}
                      type="button"
                      onClick={() => onCite(n)}
                      aria-label={`Show source ${n}: ${source.filename}, page ${source.page_number}`}
                      className="mx-0.5 inline-block min-w-7 rounded bg-lavender/20 px-1.5 py-0.5 text-center text-sm font-bold text-lavender-soft hover:bg-lavender/30"
                    >
                      [{n}]
                    </button>
                  );
                })}
              </span>
            );
          })}
        </p>
      ))}
    </div>
  );
}
