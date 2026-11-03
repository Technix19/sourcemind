import type { Metadata } from "next";
import { Lato } from "next/font/google";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const lato = Lato({ variable: "--font-lato", subsets: ["latin"], weight: ["400", "700", "900"] });

export const metadata: Metadata = {
  title: "SourceMind · Document intelligence",
  description: "Evidence-first document research assistant (local prototype).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={lato.variable}>
      <body className="antialiased">
        <DocumentsProvider>
          <ChatProvider>
            <AppShell>{children}</AppShell>
          </ChatProvider>
        </DocumentsProvider>
      </body>
    </html>
  );
}
