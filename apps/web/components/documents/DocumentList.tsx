"use client";

import { useState } from "react";
import { useDocuments } from "./DocumentsProvider";
import { fileKind, formatBytes, plural } from "@/lib/format";
import type { DocumentSummary } from "@/lib/types";

const BADGE: Record<string, string> = { PDF: "text-amber", MD: "text-sky-300", TXT: "text-mint" };

function Row({ doc }: { doc: DocumentSummary }) {
  const { removeDocument } = useDocuments();
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);
  const kind = fileKind(doc.name);

  return (
    <li className="flex items-center gap-4 rounded-xl border border-line bg-panel px-4 py-3">
      <span className={`grid size-11 shrink-0 place-items-center rounded-lg bg-surface text-xs font-black ${BADGE[kind] ?? "text-lavender"}`}>
        {kind}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold">{doc.name}</p>
        <p className="text-sm text-muted">
          {formatBytes(doc.size_bytes)} · {plural(doc.page_count, "page")} · {plural(doc.chunk_count, "passage")}
        </p>
      </div>
      <span className="rounded-full bg-mint/15 px-3 py-1 text-xs font-bold text-mint">
        {doc.status === "ready" ? "Ready" : doc.status}
      </span>
      {confirming ? (
        <span className="flex gap-2" role="group" aria-label={`Confirm removing ${doc.name}`}>
          <button
            type="button"
            disabled={removing}
            onClick={async () => {
              setRemoving(true);
              await removeDocument(doc.id);
            }}
            className="rounded-lg bg-danger/20 px-3 py-1.5 text-sm font-bold text-danger hover:bg-danger/30 disabled:opacity-50"
          >
            {removing ? "Removing…" : "Confirm"}
          </button>
          <button type="button" onClick={() => setConfirming(false)} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:text-text">
            Cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          aria-label={`Remove ${doc.name}`}
          className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-surface hover:text-text"
        >
          Remove
        </button>
      )}
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
