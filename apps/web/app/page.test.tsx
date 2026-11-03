import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, listDocuments: vi.fn(), getHealth: vi.fn(), askQuestion: vi.fn(), uploadDocument: vi.fn(), deleteDocument: vi.fn() };
});

import * as api from "@/lib/api";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import type { DocumentSummary, QueryResponse } from "@/lib/types";
import AskPage from "./page";

const DOC: DocumentSummary = { id: "d1", name: "paper.pdf", size_bytes: 1000, page_count: 2, chunk_count: 2, status: "ready" };

const evidence = (n: number) => ({
  citation_id: String(n), chunk_id: `c${n}`, document_id: "d1", filename: "paper.pdf",
  page_number: n + 1, excerpt: `Excerpt number ${n}`, score: 0.42,
});

const response = (over: Partial<QueryResponse> = {}): QueryResponse => ({
  answer_mode: "sources_only", answer: null, insufficient_evidence: false,
  evidence: [evidence(1), evidence(2)], model_used: null, request_id: "r", notice: null, ...over,
});

function setup({ docs = [DOC], generation = false } = {}) {
  vi.mocked(api.listDocuments).mockResolvedValue(docs);
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", version: "t", environment: "test", generation_available: generation });
  render(
    <DocumentsProvider>
      <ChatProvider>
        <AskPage />
      </ChatProvider>
    </DocumentsProvider>,
  );
}

const box = () => screen.getByRole("textbox", { name: /ask a question/i });
const user = () => userEvent.setup();

beforeEach(() => vi.mocked(api.askQuestion).mockReset());

// Error and cancel paths live in page.errors.test.tsx (they run through the real fetch layer).
describe("Ask page", () => {
  it("blocks asking until a document exists", async () => {
    setup({ docs: [] });
    await waitFor(() => expect(box()).toBeDisabled());
    expect(screen.getByRole("link", { name: /upload a document/i })).toBeInTheDocument();
  });

  it("asks with the keyboard and shows evidence-only results with page numbers", async () => {
    vi.mocked(api.askQuestion).mockResolvedValue(response());
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().type(box(), "Which classifier?{Enter}");

    expect(await screen.findByText(/No answer was generated/)).toBeInTheDocument();
    expect(screen.getByText("Evidence only")).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Source 2: paper.pdf, page 3" })).toBeInTheDocument();
    expect(screen.getByText(/Excerpt number 1/)).toBeInTheDocument();
    expect(api.askQuestion).toHaveBeenCalledWith("Which classifier?", "sources_only", expect.any(AbortSignal));
    expect(box()).toHaveValue(""); // cleared after sending
  });

  it("does not send a question that is too short", async () => {
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().type(box(), "hi");
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
    await user().type(box(), "{Enter}");
    expect(api.askQuestion).not.toHaveBeenCalled();
  });

  it("shows the generate option only when the server can generate", async () => {
    setup({ generation: false });
    await waitFor(() => expect(box()).toBeEnabled());
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("requests a generated answer and lets a citation jump to its evidence card", async () => {
    vi.mocked(api.askQuestion).mockResolvedValue(
      response({ answer_mode: "generated", answer: "It uses a forest [2].", model_used: "m1" }),
    );
    setup({ generation: true });
    await waitFor(() => expect(box()).toBeEnabled());
    await user().click(await screen.findByRole("checkbox"));
    await user().type(box(), "How does it decide?{Enter}");

    expect(api.askQuestion).toHaveBeenCalledWith("How does it decide?", "generated", expect.any(AbortSignal));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    await user().click(screen.getByRole("button", { name: /show source 2/i }));
    const card = screen.getByRole("article", { name: /source 2/i });
    await waitFor(() => expect(card).toHaveFocus());
    expect(card.className).toContain("border-lavender");
  });

  it("reports insufficient evidence instead of inventing an answer", async () => {
    vi.mocked(api.askQuestion).mockResolvedValue(response({ insufficient_evidence: true, evidence: [] }));
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().type(box(), "galaxies and nebulae{Enter}");
    expect(await screen.findByText(/couldn't find enough evidence/i)).toBeInTheDocument();
    expect(screen.getByText("Not enough evidence")).toBeInTheDocument();
    expect(screen.getByText(/No passages were similar enough/)).toBeInTheDocument();
  });

  it("shows a fallback notice from the server", async () => {
    vi.mocked(api.askQuestion).mockResolvedValue(response({ notice: "Answer generation is unavailable right now; showing retrieved evidence." }));
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().type(box(), "anything here{Enter}");
    expect(await screen.findByText(/generation is unavailable/i)).toBeInTheDocument();
  });

  it("quick-start prompts fill the box but never send", async () => {
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().click(screen.getByRole("button", { name: /find key findings/i }));
    expect(box()).toHaveValue("What are the key findings?");
    expect(api.askQuestion).not.toHaveBeenCalled();
  });

  it("starts over with New conversation", async () => {
    vi.mocked(api.askQuestion).mockResolvedValue(response());
    setup();
    await waitFor(() => expect(box()).toBeEnabled());
    await user().type(box(), "first question{Enter}");
    await screen.findByText("Evidence only");
    await user().click(screen.getByRole("button", { name: /new conversation/i }));
    expect(screen.queryByText("Evidence only")).toBeNull();
    expect(screen.getByText(/Answers worth/)).toBeInTheDocument();
  });
});
