"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "./AuthProvider";

function Splash({ text = "Loading…" }: { text?: string }) {
  return (
    <div role="status" className="grid min-h-screen place-items-center text-muted">
      {text}
    </div>
  );
}

/**
 * Decides what may be on screen. Private pages are NEVER rendered while signed out
 * (not even briefly), and everything per-user lives under providers keyed by the user id,
 * so signing out or switching accounts destroys documents, conversation and evidence.
 * This guard is a convenience: the real enforcement is the API rejecting unauthenticated calls.
 */
export function AppGate({ children }: { children: React.ReactNode }) {
  const { state, configured } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const onLogin = pathname === "/login";

  useEffect(() => {
    if (state.status === "signedOut" && !onLogin) router.replace("/login");
    if (state.status === "signedIn" && onLogin) router.replace("/");
  }, [state.status, onLogin, router]);

  if (!configured) return <>{onLogin ? children : <Splash text="Redirecting…" />}</>;
  if (state.status === "loading") return <Splash />;
  if (state.status === "signedOut") return onLogin ? <>{children}</> : <Splash text="Redirecting to sign in…" />;
  if (onLogin) return <Splash text="Redirecting…" />;

  return (
    <DocumentsProvider key={state.user.id}>
      <ChatProvider key={state.user.id}>
        <AppShell>{children}</AppShell>
      </ChatProvider>
    </DocumentsProvider>
  );
}
