"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { setUnauthorizedHandler } from "@/lib/api";
import { isConfigured, supabase } from "@/lib/supabase";

export type AuthUser = { id: string; email: string };

type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "signedIn"; user: AuthUser };

type AuthContextValue = {
  state: AuthState;
  configured: boolean;
  /** Shown on the login page, e.g. after the session expired. */
  notice: string | null;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

function toState(session: Session | null): AuthState {
  return session ? { status: "signedIn", user: { id: session.user.id, email: session.user.email ?? "" } } : { status: "signedOut" };
}

/** Turn provider errors into safe, friendly text. Never echo raw server messages. */
function friendly(error: { message?: string; status?: number; code?: string }, mode: "in" | "up"): string {
  if (error.status === 429 || error.code === "over_request_rate_limit") return "Too many attempts. Wait a minute and try again.";
  if (error.code === "weak_password") return "Choose a stronger password (at least 8 characters).";
  if (mode === "in") return "Incorrect email or password.";
  return "Could not create the account. If you already have one, sign in instead.";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(isConfigured ? { status: "loading" } : { status: "signedOut" });
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return;
    // The first callback is INITIAL_SESSION, so no separate getSession() call is needed.
    // Do not call other supabase methods inside this callback (documented deadlock risk).
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setState(toState(session)));
    return () => data.subscription.unsubscribe();
  }, []);

  const signOut = useCallback(async () => {
    // scope "local" ends only THIS browser's session; the default would sign out every device.
    await supabase?.auth.signOut({ scope: "local" });
    setState({ status: "signedOut" });
  }, []);

  // If the API says our token is no longer valid, sign out and say why.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setNotice("Your session expired. Please sign in again.");
      void signOut();
    });
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) return "The app is not configured.";
    setNotice(null);
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    return error ? friendly(error, "in") : null;
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) return "The app is not configured.";
    setNotice(null);
    const { data, error } = await supabase.auth.signUp({ email: email.trim(), password });
    if (error) return friendly(error, "up");
    // With email confirmation on, there is no session yet.
    if (!data.session) return "Check your email to confirm your account, then sign in.";
    return null;
  }, []);

  const value = useMemo(
    () => ({ state, configured: isConfigured, notice, signIn, signUp, signOut }),
    [state, notice, signIn, signUp, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
