"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/components/chat/ChatProvider";
import { EvidenceDrawer } from "@/components/chat/EvidenceDrawer";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { QuestionForm } from "@/components/chat/QuestionForm";
import { QuickStart } from "@/components/chat/QuickStart";
import { SourceHealth } from "@/components/chat/SourceHealth";
import { TurnView } from "@/components/chat/TurnView";
import { UploadZone } from "@/components/documents/UploadZone";

export default function AskPage() {
  const { turns, clear } = useChat();
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const started = turns.length > 0;

  // Keep the newest exchange in view; "auto" (not smooth) so reduced-motion users aren't animated.
  useEffect(() => {
    if (started) end.current?.scrollIntoView({ block: "end", behavior: "auto" });
  }, [turns, started]);

  return (
    <div className="mx-auto grid max-w-6xl gap-8 xl:grid-cols-[1fr_24rem]">
      <section className="min-w-0">
        {!started ? (
          <div className="space-y-8">
            <div>
              <p className="text-xs font-bold tracking-wider text-lavender">YOUR RESEARCH WORKSPACE</p>
              <h1 className="mt-2 text-4xl font-black leading-tight sm:text-5xl">
                Answers worth <span className="text-lavender">trusting.</span>
              </h1>
              <p className="mt-3 text-lg text-muted">Upload a document, ask a precise question, and trace each answer back to its source.</p>
            </div>
            <UploadZone />
            <QuickStart onPick={setDraft} />
          </div>
        ) : (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h1 className="text-xs font-bold tracking-wider text-lavender">CONVERSATION</h1>
              <button type="button" onClick={clear} className="rounded text-sm text-muted hover:text-text">
                New conversation
              </button>
            </div>
            <div className="space-y-6">
              {turns.map((turn) => (
                <TurnView key={turn.id} turn={turn} />
              ))}
            </div>
            <div ref={end} />
          </div>
        )}
        <div className="sticky bottom-0 mt-8 bg-ink pt-3 pb-4">
          <QuestionForm draft={draft} setDraft={setDraft} />
        </div>
      </section>

      {/* On small screens evidence moves to the drawer, and the stats only show before the first question. */}
      <div className={`space-y-6 ${started ? "hidden xl:block" : ""}`}>
        <EvidencePanel />
        <SourceHealth />
      </div>
      <EvidenceDrawer />
    </div>
  );
}
