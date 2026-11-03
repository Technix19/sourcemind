"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import type { Retrieval } from "@/lib/types";
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
    <form onSubmit={submit} className="space-y-2">
      <div className="flex items-center gap-3 rounded-2xl border border-line bg-panel p-2 pl-4 focus-within:border-lavender focus-within:ring-2 focus-within:ring-lavender/40">
        <label htmlFor="question" className="sr-only">
          Ask a question about your documents
        </label>
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
          className="min-w-0 flex-1 bg-transparent py-2 outline-none focus-visible:outline-none placeholder:text-muted disabled:cursor-not-allowed"
        />
        {pending ? (
          <button type="button" onClick={stop} className="min-h-11 rounded-xl border border-line px-4 font-bold hover:bg-surface">
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={disabled || tooShort}
            className="min-h-11 rounded-xl bg-lavender-deep px-4 font-bold text-white hover:bg-lavender-deep/85 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Ask <span aria-hidden>→</span>
          </button>
        )}
      </div>
      <div id={hintId} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 px-1 text-xs text-muted">
        <span>
          {noDocs && !apiError ? (
            <>
              <Link href="/documents" className="text-lavender underline">
                Upload a document
              </Link>{" "}
              to start asking.
            </>
          ) : (
            "SourceMind can make mistakes. Always verify important details using the sources."
          )}
        </span>
        {canSearchByMeaning && (
          <fieldset className="flex items-center gap-1">
            <legend className="sr-only">Search method</legend>
            <span aria-hidden>Search by</span>
            {METHODS.map((m) => (
              <label key={m.value} title={m.hint} className="flex min-h-8 cursor-pointer items-center gap-1.5 rounded px-2">
                <input
                  type="radio"
                  name="retrieval"
                  value={m.value}
                  checked={retrieval === m.value}
                  onChange={() => setRetrieval(m.value)}
                  className="size-4 accent-lavender"
                />
                <span>{m.label}</span>
              </label>
            ))}
          </fieldset>
        )}
        {canGenerate && (
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={generate} onChange={(e) => setGenerate(e.target.checked)} className="size-4 accent-lavender" />
            <span>Generate an answer (sends the question and excerpts to the model provider)</span>
          </label>
        )}
      </div>
      <p role="status" aria-live="polite" className="sr-only">
        {pending ? "Searching your documents" : ""}
      </p>
    </form>
  );
}
