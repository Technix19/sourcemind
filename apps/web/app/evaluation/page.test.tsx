// The page is tested through the real api client, with only fetch (and the session) stubbed.
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase", () => ({ getAccessToken: async () => "test-token", supabase: null, isConfigured: true }));

import EvaluationPage from "./page";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("Evaluation page", () => {
  it("asks the API for the published results with the user's token", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => json(404, { detail: "No evaluation results have been published yet." }));
    vi.stubGlobal("fetch", fetchMock);
    render(<EvaluationPage />);
    await screen.findByText("No evaluation has been published yet");
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/evaluation\/latest$/);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer test-token");
  });

  it("says nothing is published rather than inventing numbers when there are no results", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(404, { detail: "none" })));
    render(<EvaluationPage />);
    expect(await screen.findByText("No evaluation has been published yet")).toBeInTheDocument();
    expect(screen.getByText(/only shows measured, reproducible results/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Recall@|MRR/);
  });

  it("shows a loading state first", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<EvaluationPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading results");
  });

  it("reports a server problem as an alert", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(503, { detail: "The published evaluation results could not be read." })));
    render(<EvaluationPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be read");
  });
});
