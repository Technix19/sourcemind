"use client";

import { useRef, useState } from "react";
import { DocumentList, PendingUploads } from "@/components/documents/DocumentList";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { plural } from "@/lib/format";

export default function DocumentsPage() {
  const { documents, uploadFiles, message } = useDocuments();
  const [filter, setFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const passages = documents.reduce((sum, d) => sum + d.chunk_count, 0);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black">Your documents</h1>
          <p className="mt-1 text-muted">
            {plural(documents.length, "file")} in this workspace · {plural(passages, "searchable passage")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="rounded-xl bg-lavender-deep px-5 py-2.5 font-bold text-white hover:bg-lavender-deep/85"
        >
          + Upload documents
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          className="sr-only"
          aria-label="Choose documents to upload"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) void uploadFiles(files);
            e.target.value = "";
          }}
        />
      </div>

      <label className="mb-4 block">
        <span className="sr-only">Search documents by name</span>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search documents by name…"
          className="w-full rounded-xl border border-line bg-panel px-4 py-3 placeholder:text-muted"
        />
      </label>

      <p role="status" aria-live="polite" className={`mb-3 text-sm ${message?.kind === "error" ? "text-danger" : "text-mint"}`}>
        {message?.text}
      </p>
      <PendingUploads />
      <DocumentList filter={filter} />
      <p className="mt-6 rounded-xl bg-lavender/10 px-4 py-3 text-sm text-lavender">
        Indexed files are searchable. Scanned-only PDFs need OCR before they can be used, and OCR is not supported yet.
      </p>
    </div>
  );
}
