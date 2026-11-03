import type { Metadata } from "next";
import { Lato } from "next/font/google";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const lato = Lato({ variable: "--font-lato", subsets: ["latin"], weight: ["400", "700", "900"] });

export const metadata: Metadata = {
  title: { default: "SourceMind · Document intelligence", template: "%s · SourceMind" },
  description: "Evidence-first document research assistant (local prototype).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={lato.variable}>
      <body className="antialiased">
        <a
          href="#main"
          className="sr-only z-50 rounded-lg bg-lavender-deep px-4 py-2 font-bold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to main content
        </a>
        <DocumentsProvider>
          <ChatProvider>
            <AppShell>{children}</AppShell>
          </ChatProvider>
        </DocumentsProvider>
      </body>
    </html>
  );
}
