/**
 * Content-Security-Policy for the web app (M7c-3).
 *
 * Scripts run only if they carry this request's random nonce (or were loaded by such a script).
 * That is what blocks injected <script> tags and inline event handlers, the usual XSS payloads.
 * Network calls are limited to this site, the SourceMind API and Supabase, so a script that did
 * run could not send data anywhere else.
 */

export type CspOptions = {
  nonce: string;
  isDev: boolean;
  /** Where the browser may send API calls, e.g. http://localhost:8000. */
  apiUrl: string;
  /** The Supabase project URL (sign-in). */
  supabaseUrl: string;
};

/** Scheme + host + port only. An unusable value yields null, so it cannot widen the policy. */
export function originOf(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.origin : null;
  } catch {
    return null;
  }
}

export function buildCsp({ nonce, isDev, apiUrl, supabaseUrl }: CspOptions): string {
  const api = originOf(apiUrl);
  const supabase = originOf(supabaseUrl);
  const connect = ["'self'", api, supabase].filter((v): v is string => v !== null);
  const directives = [
    "default-src 'self'",
    // 'unsafe-eval' only in development: React uses eval there for readable error stacks.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  // Upgrading would break an http API (local development), so only ask for it when the API is https.
  if (api?.startsWith("https:")) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

export function makeNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes));
}
