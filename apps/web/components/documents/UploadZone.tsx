"use client";

import { useRef, useState } from "react";
import { useDocuments } from "./DocumentsProvider";
import { MAX_DOCUMENTS } from "@/lib/limits";

/** Drag-and-drop / browse upload area. States: idle, dragging, uploading, success, failed. */
export function UploadZone() {
  const { uploadFiles, uploads, message, documents } = useDocuments();
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const busy = uploads.some((u) => u.status === "uploading");
  const full = documents.length >= MAX_DOCUMENTS;

  const handle = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length) void uploadFiles(files);
    if (input.current) input.current.value = ""; // allow re-selecting the same file
  };

  return (
    <div className="rounded-2xl border border-line bg-panel p-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handle(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? "border-lavender bg-lavender/10" : "border-lavender-deep/50 bg-ink/40"
        }`}
      >
        <span aria-hidden className="text-3xl font-light text-lavender">
          +
        </span>
        <p className="text-lg font-bold">Drop documents here</p>
        <p className="text-sm text-muted">
          or{" "}
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={full}
            className="rounded text-lavender underline underline-offset-2 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
          >
            browse your files
          </button>{" "}
          to upload
        </p>
        <p className="mt-1 rounded-full bg-lavender/15 px-3 py-1 text-xs font-bold tracking-wide text-lavender">
          PDF · TXT · MD &nbsp;|&nbsp; 12 MB max
        </p>
        <input
          ref={input}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          className="sr-only"
          aria-label="Choose documents to upload"
          onChange={(e) => handle(e.target.files)}
        />
      </div>

      {full && <p className="mt-3 px-1 text-sm text-amber">Library is full ({MAX_DOCUMENTS} documents). Remove one to add another.</p>}
      {busy && <p className="mt-3 px-1 text-sm text-muted">Uploading and indexing…</p>}
      {/* Polite live region so screen readers hear upload results. */}
      <p
        role="status"
        aria-live="polite"
        className={`mt-3 px-1 text-sm ${message ? (message.kind === "success" ? "text-mint" : "text-danger") : "sr-only"}`}
      >
        {message?.text}
      </p>
    </div>
  );
}
