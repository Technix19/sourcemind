"use client";

import { useRef, useState } from "react";
import { DocumentList, PendingUploads } from "@/components/documents/DocumentList";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { UiIcon } from "@/components/ui/UiIcon";
import { plural } from "@/lib/format";
import { MAX_DOCUMENTS } from "@/lib/limits";

export default function DocumentsPage() {
  const { documents, uploadFiles, message } = useDocuments();
  const [filter, setFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const passages = documents.reduce((sum, doc) => sum + doc.chunk_count, 0);
  const full = documents.length >= MAX_DOCUMENTS;

  return (
    <div className="mx-auto max-w-[1350px]">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="sm-page-title">Documents</h1>
          <p className="mt-2 text-sm text-muted">Upload and manage the sources used in your research.</p>
        </div>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={full}
          className="sm-primary"
        >
          <UiIcon name="upload" size={16} />
          Upload documents
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

      <div className="mb-5 flex flex-wrap gap-2 text-[12px] text-muted">
        <span className="rounded-md border border-line bg-white dark:bg-[#1a1b2b] px-3 py-2">
          <strong className="sm-metric text-text">{documents.length}</strong> {documents.length === 1 ? "document" : "documents"}
        </span>
        <span className="rounded-md border border-line bg-white dark:bg-[#1a1b2b] px-3 py-2">
          <strong className="sm-metric text-text">{passages}</strong> {passages === 1 ? "searchable passage" : "searchable passages"}
        </span>
        <span className="rounded-md border border-line bg-white dark:bg-[#1a1b2b] px-3 py-2">
          <strong className="text-text">{MAX_DOCUMENTS - documents.length}</strong> upload slots remaining
        </span>
      </div>

      <div className="sm-panel overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <label className="relative block min-w-[240px] flex-1">
            <span className="sr-only">Search documents by name</span>
            <UiIcon name="search" size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search documents by name…"
              className="sm-field pl-10"
            />
          </label>
          <span className="text-xs text-muted">{plural(documents.length, "file")} in library</span>
        </div>

        <div className="px-4">
          <p role="status" aria-live="polite" className={message ? "py-2 text-sm " + (message.kind === "error" ? "text-danger" : "text-mint") : "sr-only"}>
            {message?.text}
          </p>
          <PendingUploads />
        </div>
        <DocumentList filter={filter} />
      </div>

      {full && <p className="mt-3 text-sm text-amber">Your library is full. Remove a document to add another.</p>}
      <p className="mt-4 flex items-start gap-2.5 text-xs leading-relaxed text-muted">
        <UiIcon name="info" size={16} className="mt-0.5 shrink-0" />
        Indexed files are searchable. Scanned-only PDFs need OCR before they can be used, and OCR is not supported yet.
      </p>
    </div>
  );
}
