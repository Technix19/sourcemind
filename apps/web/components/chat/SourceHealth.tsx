"use client";

import Link from "next/link";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { UiIcon } from "@/components/ui/UiIcon";
import { plural } from "@/lib/format";

export function SourceHealth() {
  const { documents } = useDocuments();
  const passages = documents.reduce((sum, doc) => sum + doc.chunk_count, 0);

  return (
    <section aria-label="Your sources" className="sm-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
        <h2 className="text-[14px] font-bold">Sources</h2>
        <span className="text-xs text-muted">{plural(documents.length, "document")}</span>
      </div>
      {documents.length === 0 ? (
        <div className="px-4 py-7 text-center">
          <UiIcon name="file" size={25} className="mx-auto mb-3 text-[#8190a7] dark:text-[#abaac6]" />
          <p className="text-sm font-bold">No documents yet</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">Upload a PDF, text, or Markdown file to start your research.</p>
          <Link href="/documents" className="sm-secondary mt-4">Go to documents</Link>
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-start gap-2.5 px-4 py-3">
              <UiIcon name="file" size={17} className="mt-0.5 shrink-0 text-[#69758d] dark:text-[#abaac6]" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-bold" title={doc.name}>{doc.name}</p>
                <p className="mt-1 text-[11px] text-muted">{plural(doc.page_count, "page")} · {plural(doc.chunk_count, "passage")}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
      {documents.length > 0 && (
        <div className="flex items-center justify-between border-t border-line bg-ink px-4 py-3 text-xs">
          <span className="text-muted">{plural(passages, "searchable passage")}</span>
          <Link href="/documents" className="font-bold text-lavender hover:underline">Manage sources</Link>
        </div>
      )}
    </section>
  );
}
