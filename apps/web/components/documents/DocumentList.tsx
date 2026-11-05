"use client";

import { useState } from "react";
import { useDocuments } from "./DocumentsProvider";
import { fileKind, formatBytes, plural } from "@/lib/format";
import { openDocumentPage, openErrorMessage } from "@/lib/openDocument";
import { UiIcon } from "@/components/ui/UiIcon";
import type { DocumentSummary } from "@/lib/types";

const BADGE: Record<string, string> = { PDF: "bg-red-50 text-red-700", MD: "bg-blue-50 text-blue-700", TXT: "bg-teal-50 text-teal-700" };

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
    <li className="grid grid-cols-1 gap-3 border-b border-line px-4 py-4 last:border-0 lg:grid-cols-[minmax(180px,2fr)_75px_72px_82px_minmax(125px,1fr)_minmax(160px,1.1fr)] lg:items-center lg:gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <span className={"grid size-10 shrink-0 place-items-center rounded-lg text-[10px] font-black " + (BADGE[kind] ?? "bg-indigo-50 text-lavender")}>
          {kind}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-bold text-text" title={doc.name}>{doc.name}</p>
          <p className="mt-1 text-[11px] text-muted lg:hidden">{formatBytes(doc.size_bytes)} · {plural(doc.page_count, "page")} · {plural(doc.chunk_count, "passage")}</p>
        </div>
      </div>
      <p className="hidden text-xs text-muted lg:block sm-metric">{formatBytes(doc.size_bytes)}</p>
      <p className="hidden text-xs text-muted lg:block sm-metric">{doc.page_count}</p>
      <p className="hidden text-xs text-muted lg:block sm-metric">{doc.chunk_count}</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className={"rounded-md px-2 py-1 text-[11px] font-bold " + (doc.status === "ready" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber")}>
          {doc.status === "ready" ? "Ready" : doc.status}
        </span>
        {!doc.semantic && (
          <span className="text-[11px] text-muted" title="Not indexed for meaning search. Upload it again to enable it.">Keyword only</span>
        )}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 lg:justify-end">
        {doc.has_file ? (
          <button
            type="button"
            onClick={() => void openFile()}
            disabled={opening}
            aria-label={`Open ${doc.name} in a new tab`}
            className="min-h-9 rounded-md px-2.5 text-[12px] font-bold text-lavender hover:bg-indigo-50 disabled:opacity-60"
          >
            {opening ? "Opening…" : "Open"}
          </button>
        ) : (
          <span className="text-[11px] text-muted" title="Uploaded before original files were stored. Upload it again to enable opening.">File not stored</span>
        )}
        {confirming ? (
          <span className="flex flex-wrap gap-1" role="group" aria-label={`Confirm removing ${doc.name}`}>
            <button
              type="button"
              disabled={removing}
              onClick={async () => {
                setRemoving(true);
                await removeDocument(doc.id);
              }}
              className="min-h-9 rounded-md bg-red-50 px-2.5 text-[12px] font-bold text-danger hover:bg-red-100 disabled:opacity-50"
            >
              {removing ? "Removing…" : "Confirm"}
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="min-h-9 rounded-md px-2.5 text-[12px] text-muted hover:bg-ink">Cancel</button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-label={`Remove ${doc.name}`}
            className="min-h-9 rounded-md px-2.5 text-[12px] text-muted hover:bg-red-50 hover:text-danger"
          >
            Remove
          </button>
        )}
        <p role="alert" className={openError ? "w-full text-[11px] text-danger" : "sr-only"}>{openError}</p>
      </div>
    </li>
  );
}

export function PendingUploads() {
  const { uploads, dismissUpload } = useDocuments();
  if (!uploads.length) return null;
  return (
    <ul className="space-y-2 pb-3" aria-label="Uploads in progress">
      {uploads.map((u) => (
        <li key={u.key} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-ink px-3 py-2.5 text-xs">
          <span className={u.status === "failed" ? "font-bold text-danger" : "font-bold text-amber"}>{u.status === "failed" ? "Failed" : "Processing"}</span>
          <span className="min-w-0 flex-1 truncate">
            <strong>{u.name}</strong>
            {u.error && <span className="text-muted"> — {u.error}</span>}
          </span>
          {u.status === "failed" && (
            <button type="button" onClick={() => dismissUpload(u.key)} className="rounded px-2 py-1 text-muted hover:text-text">Dismiss</button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function DocumentList({ filter = "" }: { filter?: string }) {
  const { documents, loaded, apiError } = useDocuments();
  const shown = documents.filter((d) => d.name.toLowerCase().includes(filter.trim().toLowerCase()));

  if (!loaded) return <div role="status" className="px-4 py-10 text-center text-sm text-muted">Loading documents…</div>;
  if (apiError && !documents.length) return null;
  if (!documents.length) {
    return (
      <div className="flex flex-col items-center px-6 py-14 text-center">
        <span className="mb-4 grid size-12 place-items-center rounded-xl bg-ink text-[#8692a7]">
          <UiIcon name="file" size={25} />
        </span>
        <p className="text-sm font-bold">No documents yet</p>
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted">Upload a text-based PDF, TXT, or Markdown file to make its contents searchable.</p>
      </div>
    );
  }
  if (!shown.length) return <div className="px-4 py-10 text-center text-sm text-muted">No documents match “{filter}”.</div>;

  return (
    <div>
      <div className="hidden grid-cols-[minmax(180px,2fr)_75px_72px_82px_minmax(125px,1fr)_minmax(160px,1.1fr)] gap-4 border-b border-line bg-[#fafbfe] px-4 py-3 text-[11px] font-bold text-muted lg:grid">
        <span>Document</span>
        <span>Size</span>
        <span>Pages</span>
        <span>Passages</span>
        <span>Status</span>
        <span className="text-right">Actions</span>
      </div>
      <ul>
        {shown.map((doc) => <Row key={doc.id} doc={doc} />)}
      </ul>
    </div>
  );
}
