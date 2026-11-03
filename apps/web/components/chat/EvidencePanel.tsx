"use client";

import { useState } from "react";
import { useChat } from "./ChatProvider";
import { plural } from "@/lib/format";
import type { Evidence } from "@/lib/types";

export const evidenceDomId = (turnId: number, citationId: string) => `evidence-${turnId}-${citationId}`;

function EvidenceCard({ turnId, item, selected }: { turnId: number; item: Evidence; selected: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const long = item.excerpt.length > 280;
  return (
    <article
      id={evidenceDomId(turnId, item.citation_id)}
      tabIndex={-1}
      aria-label={`Source ${item.citation_id}: ${item.filename}, page ${item.page_number}`}
      className={`rounded-xl border bg-surface p-4 transition-colors ${selected ? "border-lavender ring-1 ring-lavender" : "border-line"}`}
    >
      <div className="flex items-center gap-2">
        <span className="rounded-lg bg-lavender/20 px-2 py-0.5 text-sm font-bold text-lavender">[{item.citation_id}]</span>
        <p className="min-w-0 flex-1 truncate font-bold">{item.filename}</p>
      </div>
      <p className="mt-1 text-xs text-mint">
        Page {item.page_number} · Rank {item.citation_id} ·{" "}
        <span title="Lexical (keyword) similarity to your question. It is not a probability that this passage answers it.">
          match {item.score.toFixed(2)}
        </span>
      </p>
      <blockquote className={`mt-3 text-sm leading-relaxed text-text/90 ${expanded ? "" : "line-clamp-5"}`}>“{item.excerpt}”</blockquote>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 rounded text-sm font-bold text-lavender hover:text-text"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </article>
  );
}

export function EvidencePanel() {
  const { activeTurn, selection } = useChat();
  if (!activeTurn) return null;
  const evidence = activeTurn.response?.evidence ?? [];

  return (
    <section aria-label="Supporting source passages" className="rounded-2xl border border-line bg-panel p-5">
      <p className="text-xs font-bold tracking-wider text-lavender">EVIDENCE ({evidence.length})</p>
      <p className="mt-1 mb-4 font-bold">Supporting source passages</p>
      {activeTurn.status === "pending" && <p className="text-sm text-muted">Searching your documents…</p>}
      {activeTurn.status === "done" && evidence.length === 0 && (
        <p className="text-sm text-muted">No passages were similar enough to this question to show.</p>
      )}
      {(activeTurn.status === "error" || activeTurn.status === "stopped") && (
        <p className="text-sm text-muted">No evidence for this question.</p>
      )}
      <div className="space-y-3">
        {evidence.map((item) => (
          <EvidenceCard
            key={item.chunk_id}
            turnId={activeTurn.id}
            item={item}
            selected={selection?.turnId === activeTurn.id && selection.citationId === item.citation_id}
          />
        ))}
      </div>
      {evidence.length > 0 && (
        <p className="mt-4 text-xs text-muted">
          {plural(evidence.length, "passage")} retrieved by keyword matching. Read the passages before relying on any answer.
        </p>
      )}
    </section>
  );
}
