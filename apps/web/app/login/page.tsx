"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";

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
    // On success the auth listener flips the app to signed-in and the guard leaves this page.
    if (problem) setError(problem);
    else if (creating) setPassword("");
  };

  return (
    <main id="main" tabIndex={-1} className="grid min-h-screen place-items-center px-4 py-10 outline-none">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-3">
          <span aria-hidden className="grid size-11 place-items-center rounded-xl bg-lavender text-xl font-black text-ink">
            S
          </span>
          <div>
            <p className="text-2xl leading-none font-black">sourcemind</p>
            <p className="text-[10px] font-bold tracking-widest text-lavender">DOCUMENT INTELLIGENCE</p>
          </div>
        </div>

        <h1 className="text-3xl font-black">{creating ? "Create your account" : "Sign in"}</h1>
        <p className="mt-1 mb-6 text-muted">
          {creating ? "Your documents stay private to your account." : "Welcome back. Sign in to see your documents."}
        </p>

        {!configured && (
          <p role="alert" className="mb-4 rounded-xl border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-amber">
            This app is not configured yet. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local and restart.
          </p>
        )}
        {notice && !error && (
          <p role="status" className="mb-4 rounded-xl border border-line bg-panel px-4 py-3 text-sm text-muted">
            {notice}
          </p>
        )}

        <form onSubmit={submit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-bold">Email</span>
            <input
              type="email"
              name="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="min-h-11 w-full rounded-xl border border-line bg-panel px-4"
            />
          </label>

          <div>
            <label className="block">
              <span className="mb-1 block text-sm font-bold">Password</span>
              <input
                type="password"
                name="password"
                required
                minLength={creating ? 8 : undefined}
                autoComplete={creating ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-describedby={creating ? "password-hint" : undefined}
                className="min-h-11 w-full rounded-xl border border-line bg-panel px-4"
              />
            </label>
            {/* Outside the label so the field's name stays just "Password"; announced via aria-describedby. */}
            {creating && (
              <span id="password-hint" className="mt-1 block text-xs text-muted">
                At least 8 characters.
              </span>
            )}
          </div>

          <p role="alert" className={error ? "text-sm text-danger" : "sr-only"}>
            {error}
          </p>

          <button
            type="submit"
            disabled={busy || !configured}
            className="min-h-11 w-full rounded-xl bg-lavender-deep px-5 font-bold text-white hover:bg-lavender-deep/85 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Please wait…" : creating ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {creating ? "Already have an account?" : "New here?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(creating ? "in" : "up");
              setError(null);
            }}
            className="rounded font-bold text-lavender underline underline-offset-2 hover:text-text"
          >
            {creating ? "Sign in" : "Create an account"}
          </button>
        </p>
      </div>
    </main>
  );
}
