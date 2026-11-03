"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { NAV } from "./nav";

export function TopBar() {
  const pathname = usePathname();
  const { health, apiError, loaded } = useDocuments();
  const current = NAV.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href))) ?? NAV[0];
  const mode = !loaded ? "Checking…" : apiError ? "API offline" : health?.generation_available ? "AI answers available" : "Retrieval mode";

  return (
    <header className="border-b border-line px-4 py-4 sm:px-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-bold tracking-wider text-lavender">WORKSPACE / {current.crumb.toUpperCase()}</p>
          <p className="text-sm text-muted">{current.blurb}</p>
        </div>
        <p className="flex shrink-0 items-center gap-2 text-sm text-muted">
          <span aria-hidden className={`size-2 rounded-full ${apiError ? "bg-danger" : loaded ? "bg-mint" : "bg-amber"}`} />
          {mode}
        </p>
      </div>
      {/* The sidebar is hidden on small screens, so navigation lives here instead. */}
      <nav aria-label="Main (compact)" className="mt-3 flex gap-2 lg:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current.href === item.href ? "page" : undefined}
            className={`rounded-lg px-3 py-2.5 text-sm font-bold ${current.href === item.href ? "bg-lavender/20 text-lavender" : "text-muted"}`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
