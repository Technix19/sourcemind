import type { Metadata } from "next";

export const metadata: Metadata = { title: "Research workspace" };

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
