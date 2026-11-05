"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { useDocuments } from "@/components/documents/DocumentsProvider";
import { BrandLogo } from "@/components/ui/BrandLogo";
import { UiIcon, type IconName } from "@/components/ui/UiIcon";
import { NAV } from "./nav";

const icons: Record<string, IconName> = {
  "/": "message",
  "/documents": "file",
  "/evaluation": "chart",
};

export function Sidebar() {
  const pathname = usePathname();
  const { apiError, loaded } = useDocuments();
  const { state, signOut } = useAuth();
  const email = state.status === "signedIn" ? state.user.email : "";
  const online = loaded && !apiError;

  return (
    <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col overflow-y-auto border-r border-line bg-white dark:bg-[#1a1b2b] px-3.5 py-5 lg:flex">
      <Link href="/" className="mb-9 inline-flex min-h-11 items-center rounded-lg px-2">
        <BrandLogo compact />
      </Link>

      <div className="mb-6 px-2">
        <p className="sm-muted-label mb-2">Workspace</p>
        <div className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-3">
          <UiIcon name="folder" size={17} className="shrink-0 text-lavender" />
          <div className="min-w-0">
            <p className="truncate text-[13px] font-bold text-text">Research workspace</p>
            <p className="text-[11px] text-muted">Personal workspace</p>
          </div>
        </div>
      </div>

      <nav aria-label="Main" className="flex-1">
        <p className="sm-muted-label mb-2 px-2">Navigate</p>
        <ul className="space-y-0.5">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    "flex min-h-11 items-center gap-3 rounded-lg px-3 text-[13px] font-bold transition-colors " +
                    (active
                      ? "bg-[#edeefe] dark:bg-[#382953] text-[#3730a3] dark:text-[#d1bcff]"
                      : "text-[#516075] dark:text-[#b4b6cf] hover:bg-ink hover:text-text")
                  }
                >
                  <UiIcon name={icons[item.href]} size={18} />
                  <span>{item.label === "Ask questions" ? "Ask" : item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-line pt-4">
        <div className="flex items-center gap-2 px-2 text-xs text-muted">
          <span aria-hidden className={"size-2 rounded-full " + (online ? "bg-emerald-600" : loaded ? "bg-danger" : "bg-amber")} />
          <span>{online ? "Connected" : apiError ? "API offline" : "Connecting"}</span>
        </div>
        <p className="mt-2 truncate px-2 text-[13px] font-bold text-text" title={email}>{email}</p>
        <button
          type="button"
          onClick={() => void signOut()}
          className="mt-2 flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-[13px] font-medium text-muted hover:bg-ink hover:text-text"
        >
          <UiIcon name="logout" size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
