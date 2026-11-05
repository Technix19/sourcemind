import type { Metadata } from "next";
import { Lato } from "next/font/google";
import { headers } from "next/headers";
import { AppGate } from "@/components/auth/AppGate";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";

const lato = Lato({ variable: "--font-lato", subsets: ["latin"], weight: ["400", "700", "900"] });

// Rendered per request so the Content-Security-Policy nonce (see proxy.ts) reaches every script.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "SourceMind · Document intelligence", template: "%s · SourceMind" },
  description: "Research your documents with source-backed answers and verifiable evidence.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="en" className={lato.variable} suppressHydrationWarning>
      <head>
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: `(function () {
              try {
                var saved = localStorage.getItem("sourcemind.theme");
                var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
                document.documentElement.dataset.theme = saved === "light" || saved === "dark"
                  ? saved : dark ? "dark" : "light";
              } catch (_) {
                document.documentElement.dataset.theme = "light";
              }
            })();`,
          }}
        />
      </head>
      <body className="antialiased">
        <a
          href="#main"
          className="sr-only z-50 rounded-lg bg-lavender-deep px-4 py-2 font-bold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to main content
        </a>
        <AuthProvider>
          <AppGate>{children}</AppGate>
        </AuthProvider>
      </body>
    </html>
  );
}
