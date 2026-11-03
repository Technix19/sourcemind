"use client";

import { UploadZone } from "@/components/documents/UploadZone";
import { useDocuments } from "@/components/documents/DocumentsProvider";

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <p className="text-4xl font-black">{value}</p>
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}

export default function AskPage() {
  const { documents } = useDocuments();
  const passages = documents.reduce((sum, d) => sum + d.chunk_count, 0);

  return (
    <div className="mx-auto grid max-w-6xl gap-8 xl:grid-cols-[1fr_20rem]">
      <section>
        <p className="text-xs font-bold tracking-wider text-lavender">YOUR RESEARCH WORKSPACE</p>
        <h1 className="mt-2 text-5xl font-black leading-tight">
          Answers worth <span className="text-lavender">trusting.</span>
        </h1>
        <p className="mt-3 mb-8 text-lg text-muted">Upload a document, ask a precise question, and trace each answer back to its source.</p>
        <UploadZone />
        <p className="mt-6 rounded-xl border border-line bg-panel px-4 py-3 text-sm text-muted">
          Asking questions arrives in the next build step. For now you can upload and manage documents.
        </p>
      </section>

      <aside aria-label="Source health" className="h-fit rounded-2xl border border-line bg-panel p-6">
        <p className="mb-6 text-xs font-bold tracking-wider text-lavender">SOURCE HEALTH</p>
        <div className="space-y-6">
          <Stat value={String(documents.length).padStart(2, "0")} label="Documents indexed" />
          <Stat value={String(passages).padStart(3, "0")} label="Searchable passages" />
          <Stat value="—" label="Last question" />
        </div>
        <div className="mt-6 border-t border-line pt-5">
          <p className="font-bold">Evidence before answers</p>
          <p className="mt-1 text-sm text-muted">Every response will include the passages retrieved from your files, with page numbers.</p>
          <p className="mt-4 font-bold">Your data stays in memory</p>
          <p className="mt-1 text-sm text-muted">Uploaded files are not saved to a database in this local prototype. Restarting the API clears them.</p>
        </div>
      </aside>
    </div>
  );
}
