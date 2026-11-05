"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import type { Retrieval } from "@/lib/types";
import { UiIcon } from "@/components/ui/UiIcon";
import { MAX_QUESTION, MIN_QUESTION, useChat } from "./ChatProvider";

const METHODS: { value: Retrieval; label: string; hint: string }[] = [
  { value: "tfidf", label: "Keyword", hint: "Matches the words you type. Transparent, but misses rephrased wording." },
  { value: "embedding", label: "Meaning", hint: "Also finds passages that say it differently. Scores are not comparable with keyword scores." },
];

export function QuestionForm({ draft, setDraft }: { draft: string; setDraft: (value: string) => void }) {
  const { documents, health, apiError } = useDocuments();
  const { ask, stop, pending } = useChat();
  const [generate, setGenerate] = useState(false);
  const [retrieval, setRetrieval] = useState<Retrieval>("tfidf");
  const input = useRef<HTMLInputElement>(null);
  const hintId = useId();

  const canGenerate = health?.generation_available === true;
  const canSearchByMeaning = health?.meaning_search_available === true;
  const noDocs = documents.length === 0;
  const tooShort = draft.trim().length < MIN_QUESTION;
  const disabled = noDocs || !!apiError;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (disabled || pending || tooShort) return;
    const question = draft;
    setDraft("");
    await ask(question, canGenerate && generate ? "generated" : "sources_only", canSearchByMeaning ? retrieval : "tfidf");
    input.current?.focus();
  };

  return (
    <form onSubmit={submit} className="sm-panel overflow-hidden">
      <div className="flex min-h-[65px] items-center gap-3 px-4 py-2 focus-within:bg-[#fbfcff] dark:focus-within:bg-[#252437]">
        <label htmlFor="question" className="sr-only">Ask a question about your documents</label>
        <input
          id="question"
          ref={input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={MAX_QUESTION}
          disabled={disabled}
          autoComplete="off"
          aria-describedby={hintId}
          placeholder={noDocs ? "Upload a document first…" : "Ask about your documents…"}
          className="min-w-0 flex-1 bg-transparent py-2 text-[14px] text-text outline-none placeholder:text-muted focus-visible:outline-none disabled:cursor-not-allowed"
        />
        {pending ? (
          <button type="button" onClick={stop} className="sm-secondary">Stop</button>
        ) : (
          <button type="submit" disabled={disabled || tooShort} className="sm-primary">
            Ask
            <UiIcon name="send" size={15} />
          </button>
        )}
      </div>
      <div id={hintId} className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2 border-t border-line bg-[#fbfcfe] dark:bg-[#181a2b] px-4 py-2.5 text-xs text-muted">
        <span className="order-3 w-full text-[11px] leading-relaxed sm:order-none sm:w-auto">
          {noDocs && !apiError ? (
            <>
              <Link href="/documents" className="font-bold text-lavender hover:underline">Upload a document</Link>{" "}
              to start asking.
            </>
          ) : (
            "Check citations before relying on an answer."
          )}
        </span>
        <div className="flex flex-wrap items-center gap-3">
          {canSearchByMeaning && (
            <fieldset className="flex items-center gap-2.5">
              <legend className="sr-only">Search method</legend>
              <span aria-hidden="true" className="text-[11px] text-muted">Search by</span>
              {METHODS.map((m) => (
                <label key={m.value} title={m.hint} className="flex min-h-7 cursor-pointer items-center gap-1.5">
                  <input
                    type="radio"
                    name="retrieval"
                    value={m.value}
                    checked={retrieval === m.value}
                    onChange={() => setRetrieval(m.value)}
                    className="size-3.5 accent-lavender"
                  />
                  <span>{m.label}</span>
                </label>
              ))}
            </fieldset>
          )}
          {canGenerate && (
            <label className="flex cursor-pointer items-center gap-1.5">
              <input type="checkbox" checked={generate} onChange={(e) => setGenerate(e.target.checked)} className="size-3.5 accent-lavender" />
              <span>Generate an answer (sends the question and excerpts to the model provider)</span>
            </label>
          )}
        </div>
      </div>
      <p role="status" aria-live="polite" className="sr-only">{pending ? "Searching your documents" : ""}</p>
    </form>
  );
}
