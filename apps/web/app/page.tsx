import type { Metadata } from "next";
import LandingPage from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "SourceMind | Document research with verifiable evidence",
  description: "Search your documents, ask questions, and check the original source passages with SourceMind.",
};

export default function HomePage() {
  return <LandingPage />;
}
