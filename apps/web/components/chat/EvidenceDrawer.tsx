"use client";

import { useEffect, useRef } from "react";
import { EvidencePanel } from "./EvidencePanel";
import { useChat } from "./ChatProvider";
import { XL } from "./TurnView";

/**
 * Mobile/tablet home for the evidence. A native <dialog> gives a focus trap,
 * Escape-to-close and focus restoration without custom code. On wide screens
 * the evidence is a side rail instead, so the drawer closes itself there.
 */
export function EvidenceDrawer() {
  const { drawerOpen, setDrawerOpen } = useChat();
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (drawerOpen && !el.open) el.showModal();
    if (!drawerOpen && el.open) el.close();
  }, [drawerOpen]);

  useEffect(() => {
    const query = window.matchMedia(XL);
    const onChange = () => query.matches && setDrawerOpen(false);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [setDrawerOpen]);

  return (
    <dialog
      ref={dialog}
      aria-labelledby="sources-title"
      onClose={() => setDrawerOpen(false)}
      onClick={(e) => e.target === dialog.current && setDrawerOpen(false)} // click on the backdrop
      className="m-0 mt-auto max-h-[85vh] w-full max-w-none rounded-t-2xl border border-line bg-white p-0 text-text shadow-xl backdrop:bg-slate-900/45 xl:hidden"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 id="sources-title" className="font-bold">
          Sources
        </h2>
        <button type="button" onClick={() => setDrawerOpen(false)} className="min-h-10 rounded-lg px-3 font-bold text-lavender hover:bg-surface">
          Close
        </button>
      </div>
      <div className="max-h-[calc(85vh-3.5rem)] overflow-y-auto p-4">{drawerOpen && <EvidencePanel variant="drawer" />}</div>
    </dialog>
  );
}
