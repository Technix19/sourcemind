"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, deleteDocument, getHealth, listDocuments, uploadDocument } from "@/lib/api";
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES } from "@/lib/limits";
import { formatBytes, plural } from "@/lib/format";
import type { DocumentSummary, Health } from "@/lib/types";

export type UploadItem = {
  key: string;
  name: string;
  status: "uploading" | "failed";
  error?: string;
};

export type Message = { kind: "success" | "error"; text: string };

type DocumentsContextValue = {
  documents: DocumentSummary[];
  loaded: boolean;
  health: Health | null;
  apiError: string | null;
  uploads: UploadItem[];
  message: Message | null;
  uploadFiles: (files: File[]) => Promise<void>;
  removeDocument: (id: string) => Promise<void>;
  dismissUpload: (key: string) => void;
  refresh: () => Promise<void>;
};

const DocumentsContext = createContext<DocumentsContextValue | null>(null);

export function useDocuments(): DocumentsContextValue {
  const value = useContext(DocumentsContext);
  if (!value) throw new Error("useDocuments must be used inside <DocumentsProvider>");
  return value;
}

function precheck(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))) return "Only PDF, TXT and MD files are supported.";
  if (file.size > MAX_UPLOAD_BYTES) return `This file is ${formatBytes(file.size)}; the limit is 12 MB.`;
  if (file.size === 0) return "The file is empty.";
  return null;
}

let uploadCounter = 0;

export function DocumentsProvider({ children }: { children: React.ReactNode }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [message, setMessage] = useState<Message | null>(null);

  // Fetching is separate from applying the result so the mount effect can cancel
  // a stale response and never sets state synchronously.
  const load = useCallback(async () => {
    try {
      const [docs, healthResult] = await Promise.all([listDocuments(), getHealth()]);
      return { ok: true as const, docs, health: healthResult };
    } catch (err) {
      return { ok: false as const, error: err instanceof ApiError ? err.message : "Something went wrong talking to the API." };
    }
  }, []);

  const apply = useCallback((result: Awaited<ReturnType<typeof load>>) => {
    if (result.ok) {
      setDocuments(result.docs);
      setHealth(result.health);
      setApiError(null);
    } else {
      setApiError(result.error);
    }
    setLoaded(true);
  }, []);

  const refresh = useCallback(async () => apply(await load()), [load, apply]);

  useEffect(() => {
    let cancelled = false;
    void load().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [load, apply]);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        const key = `upload-${++uploadCounter}`;
        const problem = precheck(file);
        if (problem) {
          setUploads((items) => [...items, { key, name: file.name, status: "failed", error: problem }]);
          setMessage({ kind: "error", text: `${file.name}: ${problem}` });
          continue;
        }
        setUploads((items) => [...items, { key, name: file.name, status: "uploading" }]);
        try {
          const doc = await uploadDocument(file);
          setUploads((items) => items.filter((item) => item.key !== key));
          setMessage({ kind: "success", text: `Indexed ${doc.name}: ${plural(doc.chunk_count, "searchable passage")}.` });
          await refresh();
        } catch (err) {
          const text = err instanceof ApiError ? err.message : "Upload failed.";
          setUploads((items) => items.map((item) => (item.key === key ? { ...item, status: "failed", error: text } : item)));
          setMessage({ kind: "error", text: `${file.name}: ${text}` });
        }
      }
    },
    [refresh],
  );

  const removeDocument = useCallback(
    async (id: string) => {
      try {
        await deleteDocument(id);
        setMessage({ kind: "success", text: "Document removed." });
      } catch (err) {
        // A 404 means it is already gone; refreshing below shows the true state either way.
        if (!(err instanceof ApiError && err.status === 404)) {
          setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Could not remove the document." });
        }
      }
      await refresh();
    },
    [refresh],
  );

  const dismissUpload = useCallback((key: string) => setUploads((items) => items.filter((i) => i.key !== key)), []);

  const value = useMemo(
    () => ({ documents, loaded, health, apiError, uploads, message, uploadFiles, removeDocument, dismissUpload, refresh }),
    [documents, loaded, health, apiError, uploads, message, uploadFiles, removeDocument, dismissUpload, refresh],
  );

  return <DocumentsContext.Provider value={value}>{children}</DocumentsContext.Provider>;
}
