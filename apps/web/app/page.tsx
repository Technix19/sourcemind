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
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { UiIcon } from "@/components/ui/UiIcon";
import { plural } from "@/lib/format";

export default function AskPage() {
  const { turns, clear } = useChat();
  const { documents } = useDocuments();
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const started = turns.length > 0;
  const passages = documents.reduce((total, d) => total + d.chunk_count, 0);

  useEffect(() => {
    if (started) end.current?.scrollIntoView({ block: "end", behavior: "auto" });
  }, [turns, started]);

  return (
    <div className="mx-auto max-w-[1500px]">
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="sm-page-title">Ask your documents</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Find what matters, ask follow-up questions, and check the original passages.
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-line bg-white dark:bg-[#1a1b2b] px-3 py-2 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <UiIcon name="file" size={15} />
            {plural(documents.length, "document")}
          </span>
          <span className="h-4 w-px bg-line" aria-hidden="true" />
          <span className="flex items-center gap-1.5">
            <UiIcon name="layers" size={15} />
            {plural(passages, "passage")}
          </span>
        </div>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(290px,330px)]">
        <section aria-label="Research conversation" className="min-w-0">
          {!started ? (
            <div className="space-y-6">
              {documents.length === 0 ? (
                <>
                  <UploadZone />
                  <div className="px-1">
                    <h2 className="text-[16px] font-bold text-text">Get started with a question</h2>
                    <p className="mt-1 text-sm text-muted">Answers worth checking begin with documents you can inspect.</p>
                  </div>
                </>
              ) : (
                <div className="sm-panel px-5 py-5">
                  <div className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-lg bg-[#eef0ff] dark:bg-[#33284e] text-lavender">
                      <UiIcon name="check" size={19} />
                    </span>
                    <div>
                      <h2 className="text-sm font-bold">Your sources are ready</h2>
                      <p className="mt-0.5 text-xs text-muted">Ask a question, then review the supporting evidence.</p>
                    </div>
                  </div>
                </div>
              )}
              <QuickStart onPick={setDraft} />
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center justify-between gap-2 border-b border-line pb-3">
                <h2 className="text-[14px] font-bold">Conversation</h2>
                <button type="button" onClick={clear} className="sm-secondary">
                  <UiIcon name="plus" size={15} />
                  New conversation
                </button>
              </div>
              <div className="space-y-6">
                {turns.map((turn) => <TurnView key={turn.id} turn={turn} />)}
              </div>
              <div ref={end} />
            </div>
          )}

          <div className="sticky bottom-0 z-10 mt-6 bg-ink/95 pb-3 pt-3 backdrop-blur-sm">
            <QuestionForm draft={draft} setDraft={setDraft} />
          </div>
        </section>

        <aside className={started ? "hidden xl:block" : ""}>
          {started ? <EvidencePanel /> : <SourceHealth />}
        </aside>
      </div>

      <EvidenceDrawer />
    </div>
  );
}
