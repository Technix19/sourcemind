"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { BrandLogo } from "@/components/ui/BrandLogo";
import { UiIcon, type IconName } from "@/components/ui/UiIcon";
import { NAV } from "./nav";

const navIcons: Record<string, IconName> = {
  "/": "message",
  "/documents": "file",
  "/evaluation": "chart",
};

export function TopBar() {
  const pathname = usePathname();
  const { health, apiError, loaded } = useDocuments();
  const { signOut } = useAuth();
  const current = NAV.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href))) ?? NAV[0];
  const mode = !loaded ? "Connecting" : apiError ? "API offline" : health?.generation_available ? "AI answers available" : "Retrieval mode";

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-white/95 px-5 backdrop-blur-sm sm:px-8">
      <div className="flex min-h-[66px] items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5 text-sm">
          <span className="lg:hidden"><BrandLogo compact /></span>
          <Link href="/" className="hidden font-medium text-muted hover:text-text lg:inline">Workspace</Link>
          <UiIcon name="arrow" size={13} className="hidden shrink-0 text-[#94a3b8] lg:inline" />
          <span className="hidden truncate font-bold text-text lg:inline">{current.crumb}</span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="inline-flex items-center gap-2 whitespace-nowrap text-[11px] font-medium text-muted sm:text-xs" role="status">
            <span aria-hidden className={"size-[7px] rounded-full " + (apiError ? "bg-danger" : loaded ? "bg-emerald-600" : "bg-amber")} />
            {mode}
          </span>
          {pathname === "/" && (
            <Link href="/documents" className="sm-secondary hidden sm:inline-flex">
              <UiIcon name="upload" size={16} />
              Documents
            </Link>
          )}
          <button
            type="button"
            onClick={() => void signOut()}
            className="sm-secondary lg:hidden"
          >
            Sign out
          </button>
        </div>
      </div>
      <nav aria-label="Main (compact)" className="flex gap-1 overflow-x-auto pb-2 lg:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current.href === item.href ? "page" : undefined}
            className={
              "flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold " +
              (current.href === item.href ? "bg-[#eef0ff] text-[#3730a3]" : "text-muted hover:bg-ink")
            }
          >
            <UiIcon name={navIcons[item.href]} size={15} />
            {item.label === "Ask questions" ? "Ask" : item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
