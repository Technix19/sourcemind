"use client";

import { useDocuments } from "@/components/documents/DocumentsProvider";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { apiError, refresh } = useDocuments();

  return (
    <div className="flex min-h-screen bg-ink">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        {apiError && (
          <div role="alert" className="flex items-center gap-3 border-b border-rose-200 bg-rose-50 px-5 py-3 text-sm text-danger sm:px-8">
            <span className="flex-1">{apiError}</span>
            <button type="button" onClick={() => void refresh()} className="sm-secondary shrink-0">
              Retry
            </button>
          </div>
        )}
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 outline-none sm:px-7 sm:py-8 xl:px-10">
          {children}
        </main>
      </div>
    </div>
  );
}
