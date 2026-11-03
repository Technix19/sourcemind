"use client";

import { useState } from "react";
import { useDocuments } from "./DocumentsProvider";
import { fileKind, formatBytes, plural } from "@/lib/format";
import { openDocumentPage, openErrorMessage } from "@/lib/openDocument";
import type { DocumentSummary } from "@/lib/types";

const BADGE: Record<string, string> = { PDF: "text-amber", MD: "text-sky-300", TXT: "text-mint" };

function Row({ doc }: { doc: DocumentSummary }) {
  const { removeDocument } = useDocuments();
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const kind = fileKind(doc.name);

  const openFile = async () => {
    if (opening) return;
    setOpening(true);
    setOpenError(null);
    try {
      await openDocumentPage(doc.id);
    } catch (err) {
      setOpenError(openErrorMessage(err));
    } finally {
      setOpening(false);
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-line bg-panel px-4 py-3">
      {/* On a phone the name gets its own full-width line; status and actions sit below it. */}
      <div className="flex min-w-0 basis-full items-center gap-4 sm:flex-1 sm:basis-0">
        <span className={`grid size-11 shrink-0 place-items-center rounded-lg bg-surface text-xs font-black ${BADGE[kind] ?? "text-lavender"}`}>
          {kind}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold">{doc.name}</p>
          <p className="text-sm text-muted">
            {formatBytes(doc.size_bytes)} · {plural(doc.page_count, "page")} · {plural(doc.chunk_count, "passage")}
          </p>
        </div>
      </div>
      <div className="flex w-full items-center justify-between gap-3 sm:w-auto sm:justify-end">
        <span className="rounded-full bg-mint/15 px-3 py-1 text-xs font-bold text-mint">
          {doc.status === "ready" ? "Ready" : doc.status}
        </span>
        {doc.has_file ? (
          <button
            type="button"
            onClick={() => void openFile()}
            disabled={opening}
            aria-label={`Open ${doc.name} in a new tab`}
            className="min-h-10 rounded-lg px-3 text-sm font-bold text-lavender hover:bg-surface disabled:opacity-60"
          >
            {opening ? "Opening…" : "Open"}
          </button>
        ) : (
          <span className="text-xs text-muted" title="Uploaded before original files were stored. Upload it again to enable opening.">
            File not stored
          </span>
        )}
        {confirming ? (
          <span className="flex gap-2" role="group" aria-label={`Confirm removing ${doc.name}`}>
            <button
              type="button"
              disabled={removing}
              onClick={async () => {
                setRemoving(true);
                await removeDocument(doc.id);
              }}
              className="min-h-10 rounded-lg bg-danger/20 px-3 text-sm font-bold text-danger hover:bg-danger/30 disabled:opacity-50"
            >
              {removing ? "Removing…" : "Confirm"}
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="min-h-10 rounded-lg px-3 text-sm text-muted hover:text-text">
              Cancel
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-label={`Remove ${doc.name}`}
            className="min-h-10 rounded-lg px-3 text-sm text-muted hover:bg-surface hover:text-text"
          >
            Remove
          </button>
        )}
      </div>
      <p role="alert" className={openError ? "w-full text-sm text-danger" : "sr-only"}>
        {openError}
      </p>
    </li>
  );
}

export function PendingUploads() {
  const { uploads, dismissUpload } = useDocuments();
  if (!uploads.length) return null;
  return (
    <ul className="mb-3 space-y-2" aria-label="Uploads in progress">
      {uploads.map((u) => (
        <li key={u.key} className="flex items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3 text-sm">
          <span className={u.status === "failed" ? "text-danger" : "text-amber"}>{u.status === "failed" ? "Failed" : "Processing"}</span>
          <span className="min-w-0 flex-1 truncate">
            <strong>{u.name}</strong>
            {u.error && <span className="text-muted"> — {u.error}</span>}
          </span>
          {u.status === "failed" && (
            <button type="button" onClick={() => dismissUpload(u.key)} className="rounded px-2 py-1 text-muted hover:text-text">
              Dismiss
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function DocumentList({ filter = "" }: { filter?: string }) {
  const { documents, loaded, apiError } = useDocuments();
  const shown = documents.filter((d) => d.name.toLowerCase().includes(filter.trim().toLowerCase()));

  if (!loaded) return <p className="text-muted">Loading documents…</p>;
  if (apiError && !documents.length) return null; // the shell already shows the connection error
  if (!documents.length) {
    return (
      <p className="rounded-xl border border-dashed border-line px-4 py-8 text-center text-muted">
        No documents yet. Upload a text-based PDF, TXT or Markdown file to get started.
      </p>
    );
  }
  if (!shown.length) return <p className="px-1 text-muted">No documents match “{filter}”.</p>;
  return (
    <ul className="space-y-3">
      {shown.map((doc) => (
        <Row key={doc.id} doc={doc} />
      ))}
    </ul>
  );
}
