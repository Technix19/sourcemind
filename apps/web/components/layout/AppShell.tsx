"use client";

import { useDocuments } from "@/components/documents/DocumentsProvider";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { apiError, refresh } = useDocuments();
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        {apiError && (
          <div role="alert" className="flex items-center gap-3 border-b border-danger/30 bg-danger/10 px-6 py-3 text-sm text-danger">
            <span className="flex-1">{apiError}</span>
            <button type="button" onClick={() => void refresh()} className="rounded-lg border border-danger/40 px-3 py-1 font-bold hover:bg-danger/10">
              Retry
            </button>
          </div>
        )}
        <main className="flex-1 px-6 py-8">{children}</main>
      </div>
    </div>
  );
}
