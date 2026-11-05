import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Static hardening headers. The Content-Security-Policy is per request (it carries a nonce), so it
  // is set in proxy.ts.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
  // cacheComponents / partialPrefetching were removed in M7c: they prerender a static shell at build
  // time, which cannot carry a per-request nonce, and the app used neither (no `use cache`, and a
  // signed-in-only UI that renders client-side anyway).
  turbopack: {
    // Pin the root to this app so a stray lockfile higher up can't change it.
    root: path.resolve(import.meta.dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
