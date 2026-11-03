// Error paths exercised at the fetch level, so the real lib/api.ts error handling runs too.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// These tests exercise the real lib/api.ts, which needs a session: pretend we are signed in.
vi.mock("@/lib/supabase", () => ({ getAccessToken: async () => "test-token", supabase: null, isConfigured: true }));

import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import AskPage from "./page";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const DOC = { id: "d1", name: "paper.pdf", size_bytes: 1000, page_count: 2, chunk_count: 2, status: "ready" };
const HEALTH = { status: "ok", version: "t", environment: "test", generation_available: false };

function mountWith(queryHandler: (init: RequestInit) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/api/v1/documents")) return json(200, { documents: [DOC] });
      if (url.endsWith("/api/v1/health")) return json(200, HEALTH);
      return queryHandler(init ?? {});
    }),
  );
  render(
    <DocumentsProvider>
      <ChatProvider>
        <AskPage />
      </ChatProvider>
    </DocumentsProvider>,
  );
}

const box = () => screen.getByRole("textbox", { name: /ask a question/i });

afterEach(() => vi.unstubAllGlobals());

describe("Ask page error handling", () => {
  it("shows the API's own error message and stays usable", async () => {
    mountWith(async () => json(409, { detail: "Upload at least one document before asking a question" }));
    await waitFor(() => expect(box()).toBeEnabled());
    await userEvent.type(box(), "anything here{Enter}");
    expect(await screen.findByText(/Upload at least one document/)).toBeInTheDocument();
    expect(box()).toBeEnabled();
  });

  it("explains a network failure instead of showing a raw error", async () => {
    mountWith(async () => {
      throw new TypeError("Failed to fetch");
    });
    await waitFor(() => expect(box()).toBeEnabled());
    await userEvent.type(box(), "anything here{Enter}");
    expect(await screen.findByText(/Can't reach the API/)).toBeInTheDocument();
  });

  it("summarises a validation error list without leaking its structure", async () => {
    mountWith(async () => json(422, { detail: [{ loc: ["body", "question"], msg: "too short" }] }));
    await waitFor(() => expect(box()).toBeEnabled());
    await userEvent.type(box(), "anything here{Enter}");
    expect(await screen.findByText("The request was not valid.")).toBeInTheDocument();
  });

  it("can stop a request in flight", async () => {
    mountWith(
      (init) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    await waitFor(() => expect(box()).toBeEnabled());
    await userEvent.type(box(), "slow question{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    expect(await screen.findByText("Stopped.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });
});
