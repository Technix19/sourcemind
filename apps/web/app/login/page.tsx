"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { BrandLogo } from "@/components/ui/BrandLogo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function LoginPage() {
  const { signIn, signUp, notice, configured } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const creating = mode === "up";

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    const problem = await (creating ? signUp : signIn)(email, password);
    setBusy(false);
    if (problem) setError(problem);
    else if (creating) setPassword("");
  };

  return (
    <main id="main" tabIndex={-1} className="sm-auth-shell relative grid min-h-screen place-items-center bg-[#f7f9fc] dark:bg-[#0e0d1b] px-5 py-10 outline-none">
      <div className="absolute right-5 top-5"><ThemeToggle /></div>
      <div className="w-full max-w-[440px]">
        <div className="mb-8 flex justify-center">
          <BrandLogo tagline />
        </div>
        <section className="sm-panel rounded-2xl px-6 py-8 shadow-[0_12px_40px_rgba(15,23,42,0.05)] sm:px-9 sm:py-10">
          <h1 className="text-[27px] font-black tracking-[-.035em] text-text">
            {creating ? "Create your account" : "Sign in to SourceMind"}
          </h1>
          <p className="mt-1.5 mb-7 text-[13px] leading-relaxed text-muted">
            {creating ? "Keep your documents and research private." : "Welcome back. Continue your document research."}
          </p>

          {!configured && (
            <p role="alert" className="mb-5 rounded-lg border border-amber/30 bg-amber/5 p-3 text-sm text-amber">
              This app is not configured yet. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local and restart.
            </p>
          )}
          {notice && !error && (
            <p role="status" className="mb-5 rounded-lg border border-line bg-ink p-3 text-sm text-muted">
              {notice}
            </p>
          )}

          <form onSubmit={submit} className="space-y-5">
            <label className="block">
              <span className="mb-2 block text-[13px] font-bold text-text">Email</span>
              <input
                type="email"
                name="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="sm-field"
                placeholder="you@example.com"
              />
            </label>

            <div>
              <label className="block">
                <span className="mb-2 block text-[13px] font-bold text-text">Password</span>
                <input
                  type="password"
                  name="password"
                  required
                  minLength={creating ? 8 : undefined}
                  autoComplete={creating ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-describedby={creating ? "password-hint" : undefined}
                  className="sm-field"
                  placeholder={creating ? "Create a secure password" : "Enter your password"}
                />
              </label>
              {creating && (
                <span id="password-hint" className="mt-1.5 block text-xs text-muted">
                  Use at least 8 characters.
                </span>
              )}
            </div>

            <p role="alert" className={error ? "rounded-lg bg-rose-50 dark:bg-[#442636] p-3 text-sm text-danger" : "sr-only"}>{error}</p>

            <button
              type="submit"
              disabled={busy || !configured}
              className="sm-primary w-full"
            >
              {busy ? "Please wait…" : creating ? "Create account" : "Sign in"}
            </button>
          </form>

          <p className="mt-7 text-center text-[13px] text-muted">
            {creating ? "Already have an account?" : "New here?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(creating ? "in" : "up");
                setError(null);
              }}
              className="rounded font-bold text-lavender hover:underline"
            >
              {creating ? "Sign in" : "Create an account"}
            </button>
          </p>
        </section>
        <p className="mt-6 text-center text-xs text-muted">
          Evidence-first research, built around your own documents.
        </p>
      </div>
    </main>
  );
}
