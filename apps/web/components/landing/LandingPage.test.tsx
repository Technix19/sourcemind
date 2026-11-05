import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LandingPage from "./LandingPage";

describe("SourceMind public landing", () => {
  it("shows a focused landing page with working navigation destinations", () => {
    render(<LandingPage />);
    expect(screen.getByRole("heading", { level: 1, name: /Ask your documents.*Check the evidence/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start researching/i })).toHaveAttribute("href", "/workspace");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("navigation", { name: "Landing page" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Built for answers you can verify." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Frequently asked questions" })).toBeInTheDocument();
  });

  it("does not imply commercial features, prices or endorsements", () => {
    render(<LandingPage />);
    expect(screen.queryByText(/what our customers say/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/choose your plan/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Illustrative interface preview/)).toBeInTheDocument();
    expect(screen.getByText(/The hosted demo may not support meaning-based search/)).toBeInTheDocument();
  });

  it("links every marketing section and the public project repository", () => {
    render(<LandingPage />);
    expect(document.getElementById("features")).not.toBeNull();
    expect(document.getElementById("faq")).not.toBeNull();
    expect(document.getElementById("how-it-works")).not.toBeNull();
    expect(screen.getByRole("navigation", { name: "Footer" }).querySelector('a[href="https://github.com/Technix19/sourcemind"]')).not.toBeNull();
  });
});
