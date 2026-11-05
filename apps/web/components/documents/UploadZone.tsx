"use client";

import { useRef, useState } from "react";
import { useDocuments } from "./DocumentsProvider";
import { MAX_DOCUMENTS } from "@/lib/limits";
import { UiIcon } from "@/components/ui/UiIcon";

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
    if (input.current) input.current.value = "";
  };

  return (
    <div className="sm-panel p-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handle(e.dataTransfer.files);
        }}
        className={
          "flex flex-col items-center rounded-lg border border-dashed px-5 py-9 text-center transition-colors " +
          (dragging ? "border-lavender bg-[#eef0ff]" : "border-[#cbd4e4] bg-[#fcfdff]")
        }
      >
        <span aria-hidden="true" className="mb-4 flex size-11 items-center justify-center rounded-lg border border-line bg-white text-lavender">
          <UiIcon name="upload" size={21} />
        </span>
        <p className="text-[15px] font-bold">Drop documents here</p>
        <p className="mt-2 text-[13px] text-muted">
          Or{" "}
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={full}
            className="rounded font-bold text-lavender hover:underline disabled:cursor-not-allowed disabled:opacity-50"
          >
            browse your files
          </button>{" "}
          to upload
        </p>
        <p className="mt-3 text-xs text-muted">PDF, TXT, or Markdown · Up to 12 MB per file</p>
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
      {full && <p className="mt-3 px-2 text-xs text-amber">Library is full ({MAX_DOCUMENTS} documents). Remove one to add another.</p>}
      {busy && <p className="mt-3 px-2 text-xs text-muted">Uploading and indexing…</p>}
      <p role="status" aria-live="polite" className={message ? "mt-3 px-2 text-xs " + (message.kind === "success" ? "text-mint" : "text-danger") : "sr-only"}>
        {message?.text}
      </p>
    </div>
  );
}
