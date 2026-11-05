import { describe, expect, it } from "vitest";
import { buildCsp, makeNonce, originOf } from "./csp";

const base = { nonce: "abc123", isDev: false, apiUrl: "https://api.example.com", supabaseUrl: "https://proj.supabase.co" };
const directive = (csp: string, name: string) => csp.split("; ").find((d) => d.startsWith(`${name} `)) ?? "";

describe("buildCsp", () => {
  it("allows scripts only with the request's nonce, never 'unsafe-inline' or 'unsafe-eval' in production", () => {
    const script = directive(buildCsp(base), "script-src");
    expect(script).toContain("'nonce-abc123'");
    expect(script).toContain("'strict-dynamic'");
    expect(script).not.toContain("unsafe-inline");
    expect(script).not.toContain("unsafe-eval");
  });

  it("allows 'unsafe-eval' only in development", () => {
    expect(directive(buildCsp({ ...base, isDev: true }), "script-src")).toContain("'unsafe-eval'");
  });

  it("limits network calls to this site, the API and Supabase", () => {
    expect(directive(buildCsp(base), "connect-src")).toBe(
      "connect-src 'self' https://api.example.com https://proj.supabase.co",
    );
  });

  it("reduces configured URLs to their origin, so a path or key in the value cannot leak into the policy", () => {
    const csp = buildCsp({ ...base, supabaseUrl: "https://proj.supabase.co/rest/v1/?apikey=secret" });
    expect(directive(csp, "connect-src")).toContain("https://proj.supabase.co");
    expect(csp).not.toContain("apikey");
    expect(csp).not.toContain("/rest");
  });

  it("ignores an unusable URL instead of widening the policy", () => {
    const csp = buildCsp({ ...base, apiUrl: "not a url", supabaseUrl: "javascript:alert(1)" });
    expect(directive(csp, "connect-src")).toBe("connect-src 'self'");
    expect(csp).not.toContain("javascript");
  });

  it("forbids plugins, framing, base-tag changes and form posts elsewhere", () => {
    const csp = buildCsp(base);
    for (const d of ["object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'", "default-src 'self'"]) {
      expect(csp.split("; ")).toContain(d);
    }
  });

  it("asks browsers to upgrade requests only when the API is https (an http local API must keep working)", () => {
    expect(buildCsp(base)).toContain("upgrade-insecure-requests");
    expect(buildCsp({ ...base, apiUrl: "http://localhost:8000" })).not.toContain("upgrade-insecure-requests");
  });
});

describe("originOf", () => {
  it("accepts http(s) only", () => {
    expect(originOf("http://localhost:8000/x")).toBe("http://localhost:8000");
    expect(originOf("ftp://example.com")).toBeNull();
    expect(originOf("")).toBeNull();
    expect(originOf(undefined)).toBeNull();
  });
});

describe("makeNonce", () => {
  it("is unpredictable: different every time, and long enough", () => {
    const nonces = new Set(Array.from({ length: 50 }, makeNonce));
    expect(nonces.size).toBe(50);
    expect([...nonces][0].length).toBeGreaterThanOrEqual(22);
    expect([...nonces][0]).toMatch(/^[A-Za-z0-9+/=]+$/);
  });
});
