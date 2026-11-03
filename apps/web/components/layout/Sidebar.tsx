"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { NAV } from "./nav";

export function Sidebar() {
  const pathname = usePathname();
  const { apiError, loaded } = useDocuments();
  const online = loaded && !apiError;

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-panel px-4 py-5 lg:flex">
      <Link href="/" className="mb-8 flex items-center gap-3 rounded-lg px-1">
        <span aria-hidden className="grid size-10 place-items-center rounded-xl bg-lavender text-lg font-black text-ink">
          S
        </span>
        <span>
          <span className="block text-xl font-black leading-none">sourcemind</span>
          <span className="text-[10px] font-bold tracking-widest text-lavender">DOCUMENT INTELLIGENCE</span>
        </span>
      </Link>

      <p className="mb-2 px-1 text-[11px] font-bold tracking-widest text-muted">YOUR WORKSPACE</p>
      <div className="mb-8 rounded-xl border border-line bg-ink/40 px-3 py-2.5">
        <p className="font-bold">Research workspace</p>
        <p className="text-xs text-muted">Personal · Local demo</p>
      </div>

      <nav aria-label="Main">
        <p className="mb-2 px-1 text-[11px] font-bold tracking-widest text-muted">NAVIGATION</p>
        <ul className="space-y-1">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`block min-h-11 rounded-xl px-3 py-2.5 font-bold transition-colors ${
                    active ? "bg-lavender/20 text-lavender" : "text-muted hover:bg-surface hover:text-text"
                  }`}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <p className="mt-auto flex items-center gap-2 border-t border-line pt-4 text-sm text-muted">
        <span aria-hidden className={`size-2 rounded-full ${online ? "bg-mint" : "bg-danger"}`} />
        {online ? "Local workspace" : "API offline"}
      </p>
    </aside>
  );
}
