"use client";

import { useDocuments } from "@/components/documents/DocumentsProvider";
import { useChat } from "./ChatProvider";

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <p className="text-3xl font-black">{value}</p>
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}

export function SourceHealth() {
  const { documents } = useDocuments();
  const { lastQuestion } = useChat();
  const passages = documents.reduce((sum, d) => sum + d.chunk_count, 0);
  return (
    <aside aria-label="Source health" className="h-fit rounded-2xl border border-line bg-panel p-6">
      <p className="mb-5 text-xs font-bold tracking-wider text-lavender">SOURCE HEALTH</p>
      <div className="space-y-5">
        <Stat value={String(documents.length).padStart(2, "0")} label="Documents indexed" />
        <Stat value={String(passages).padStart(3, "0")} label="Searchable passages" />
        <div>
          <p className="line-clamp-2 text-lg font-bold">{lastQuestion ?? "—"}</p>
          <p className="text-sm text-muted">Last question</p>
        </div>
      </div>
      <div className="mt-6 border-t border-line pt-5">
        <p className="font-bold">Evidence before answers</p>
        <p className="mt-1 text-sm text-muted">Every response includes the passages retrieved from your files, with page numbers.</p>
        <p className="mt-4 font-bold">Your data stays in memory</p>
        <p className="mt-1 text-sm text-muted">Uploaded files are not saved to a database in this local prototype. Restarting the API clears them.</p>
      </div>
    </aside>
  );
}
