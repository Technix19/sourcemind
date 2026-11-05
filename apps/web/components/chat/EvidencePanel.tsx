"use client";

import { useState } from "react";
import { openDocumentPage, openErrorMessage } from "@/lib/openDocument";
import { useChat } from "./ChatProvider";
import { plural } from "@/lib/format";
import type { Evidence, Retrieval } from "@/lib/types";

export type PanelVariant = "rail" | "drawer";

/**
 * The side rail and the mobile drawer can hold the same card. A modal drawer makes
 * everything behind it inert, so when it is open that is the card to focus; otherwise
 * pick whichever copy is actually displayed.
 */
export function focusEvidenceCard(turnId: number, citationId: string) {
  const all = Array.from(
    document.querySelectorAll<HTMLElement>(`[data-evidence-card][data-turn="${turnId}"][data-cid="${citationId}"]`),
  );
  const modal = document.querySelector("dialog[open]");
  const pool = modal ? all.filter((card) => modal.contains(card)) : all;
  const target = pool.find((card) => card.offsetParent !== null) ?? pool[0];
  target?.scrollIntoView({ block: "nearest" });
  target?.focus({ preventScroll: true });
}

function EvidenceCard({ turnId, item, selected, retrieval }: { turnId: number; item: Evidence; selected: boolean; retrieval: Retrieval }) {
  const [expanded, setExpanded] = useState(false);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const long = item.excerpt.length > 280;

  const openPage = async () => {
    if (opening) return;
    setOpening(true);
    setOpenError(null);
    try {
      await openDocumentPage(item.document_id, item.page_number);
    } catch (err) {
      setOpenError(openErrorMessage(err));
    } finally {
      setOpening(false);
    }
  };
  return (
    <article
      data-evidence-card
      data-turn={turnId}
      data-cid={item.citation_id}
      tabIndex={-1}
      aria-label={`Source ${item.citation_id}: ${item.filename}, page ${item.page_number}`}
      className={`rounded-lg border px-3 py-3.5 transition-colors ${selected ? "border-[#a5b4fc] bg-[#f5f6ff] ring-1 ring-[#c7d2fe]" : "border-line bg-white hover:border-[#c8d2e2]"}`}
    >
      <div className="flex items-center gap-2">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-[#eef0ff] text-[11px] font-bold text-lavender">[{item.citation_id}]</span>
        <p className="min-w-0 flex-1 truncate text-[12px] font-bold">{item.filename}</p>
      </div>
      <p className="mt-2 text-[11px] text-muted">
        Page {item.page_number} · Rank {item.citation_id} ·{" "}
        {retrieval === "embedding" ? (
          <span title="Cosine similarity between the meaning of your question and this passage. Not a probability that it answers the question, and not comparable with keyword scores.">
            similarity {item.score.toFixed(2)}
          </span>
        ) : (
          <span title="Lexical (keyword) similarity to your question. It is not a probability that this passage answers it.">
            match {item.score.toFixed(2)}
          </span>
        )}
      </p>
      <blockquote className={`mt-3 break-words text-[12px] leading-[1.8] text-[#455267] ${expanded ? "" : "line-clamp-5"}`}>“{item.excerpt}”</blockquote>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-2">
        {long && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="min-h-9 rounded text-[12px] font-bold text-lavender hover:underline"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
        <button
          type="button"
          onClick={() => void openPage()}
          disabled={opening}
          aria-label={`Open page ${item.page_number} of ${item.filename} in a new tab`}
          className="min-h-9 rounded text-sm font-bold text-lavender hover:text-text disabled:opacity-60"
        >
          {opening ? "Opening…" : "Open page →"}
        </button>
      </div>
      <p role="alert" className={openError ? "mt-1 text-sm text-danger" : "sr-only"}>
        {openError}
      </p>
    </article>
  );
}

export function EvidencePanel({ variant = "rail" }: { variant?: PanelVariant }) {
  const { activeTurn, selection } = useChat();
  if (!activeTurn) return null;
  const evidence = activeTurn.response?.evidence ?? [];

  return (
    <section aria-label="Supporting source passages" className={variant === "rail" ? "sm-panel p-4" : "p-1"}>
      <div className="mb-4 flex items-center justify-between"><h2 className="text-[14px] font-bold">Evidence &amp; sources</h2><span className="rounded-md bg-ink px-2 py-1 text-[11px] font-semibold text-muted">{evidence.length}</span></div>
      <p className="mb-4 text-[12px] leading-relaxed text-muted">Supporting source passages for this question.</p>
      {activeTurn.status === "pending" && <p className="text-sm text-muted">Searching your documents…</p>}
      {activeTurn.status === "done" && evidence.length === 0 && (
        <p className="text-sm text-muted">No passages were similar enough to this question to show.</p>
      )}
      {(activeTurn.status === "error" || activeTurn.status === "stopped") && (
        <p className="text-sm text-muted">No evidence for this question.</p>
      )}
      <div className="space-y-2.5">
        {evidence.map((item) => (
          <EvidenceCard
            key={item.chunk_id}
            turnId={activeTurn.id}
            item={item}
            retrieval={activeTurn.response?.retrieval ?? "tfidf"}
            selected={selection?.turnId === activeTurn.id && selection.citationId === item.citation_id}
          />
        ))}
      </div>
      {evidence.length > 0 && (
        <p className="mt-4 text-[11px] leading-relaxed text-muted">
          {plural(evidence.length, "passage")} retrieved by {activeTurn.response?.retrieval === "embedding" ? "meaning search" : "keyword matching"}. Read the passages before relying on any answer.
        </p>
      )}
    </section>
  );
}
