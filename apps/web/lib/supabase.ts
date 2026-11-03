import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Both values are PUBLIC by design (the publishable/anon key only does what the database's
// Row Level Security allows). The service-role key must never appear anywhere in this app.
function baseUrl(raw: string | undefined): string {
  try {
    const url = new URL((raw ?? "").trim());
    return `${url.protocol}//${url.host}`; // tolerate a pasted ".../rest/v1/"
  } catch {
    return "";
  }
}

const url = baseUrl(process.env.NEXT_PUBLIC_SUPABASE_URL);
const key = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();

export const isConfigured = Boolean(url && key);

/** null when the environment is not configured; the UI then explains what to set. */
export const supabase: SupabaseClient | null = isConfigured
  ? createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } })
  : null;

/**
 * The current access token, or null when signed out. supabase-js refreshes an expired
 * token automatically, so callers never handle expiry themselves.
 */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
