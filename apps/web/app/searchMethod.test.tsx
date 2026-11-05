import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, listDocuments: vi.fn(), getHealth: vi.fn(), askQuestion: vi.fn() };
});

import * as api from "@/lib/api";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { DocumentsProvider } from "@/components/documents/DocumentsProvider";
import type { QueryResponse, Retrieval } from "@/lib/types";
import AskPage from "./workspace/page";

const DOC = { id: "d1", name: "paper.pdf", size_bytes: 1000, page_count: 2, chunk_count: 2, status: "ready", has_file: true, semantic: true };
const evidence = { citation_id: "1", chunk_id: "c1", document_id: "d1", filename: "paper.pdf", page_number: 1, excerpt: "Excerpt", score: 0.69 };
const response = (retrieval: Retrieval, notice: string | null = null): QueryResponse => ({
  answer_mode: "sources_only", answer: null, insufficient_evidence: false, evidence: [evidence],
  model_used: null, retrieval, request_id: "r", notice,
});

function setup(meaning: boolean) {
  vi.mocked(api.listDocuments).mockResolvedValue([DOC]);
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", version: "t", environment: "t", generation_available: false, meaning_search_available: meaning });
  render(
    <DocumentsProvider>
      <ChatProvider>
        <AskPage />
      </ChatProvider>
    </DocumentsProvider>,
  );
}
const box = () => screen.getByRole("textbox", { name: /ask a question/i });
const ready = async () => waitFor(() => expect(box()).toBeEnabled());

beforeEach(() => vi.mocked(api.askQuestion).mockReset());

describe("Search method", () => {
  it("is not offered when the server has meaning search switched off", async () => {
    setup(false);
    await ready();
    expect(screen.queryByRole("group", { name: "Search method" })).toBeNull();
    vi.mocked(api.askQuestion).mockResolvedValue(response("tfidf"));
    await userEvent.type(box(), "a question here{Enter}");
    expect(api.askQuestion).toHaveBeenCalledWith("a question here", "sources_only", "tfidf", expect.any(AbortSignal));
  });

  it("defaults to keyword search", async () => {
    setup(true);
    await ready();
    const group = await screen.findByRole("group", { name: "Search method" });
    expect(group).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Keyword" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Meaning" })).not.toBeChecked();
  });

  it("sends the chosen method with the question and keeps the choice for the next one", async () => {
    setup(true);
    await ready();
    vi.mocked(api.askQuestion).mockResolvedValue(response("embedding"));
    await userEvent.click(await screen.findByRole("radio", { name: "Meaning" }));
    await userEvent.type(box(), "first question{Enter}");
    expect(api.askQuestion).toHaveBeenLastCalledWith("first question", "sources_only", "embedding", expect.any(AbortSignal));
    await screen.findByText("Meaning search");
    await userEvent.type(box(), "second question{Enter}");
    await waitFor(() => expect(api.askQuestion).toHaveBeenCalledTimes(2));
    expect(api.askQuestion).toHaveBeenLastCalledWith("second question", "sources_only", "embedding", expect.any(AbortSignal));
  });

  it("can be changed from the keyboard", async () => {
    setup(true);
    await ready();
    const keyword = await screen.findByRole("radio", { name: "Keyword" });
    keyword.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Meaning" })).toBeChecked();
  });

  it("says which method found the evidence and words the score accordingly", async () => {
    setup(true);
    await ready();
    vi.mocked(api.askQuestion).mockResolvedValueOnce(response("embedding"));
    await userEvent.click(await screen.findByRole("radio", { name: "Meaning" }));
    await userEvent.type(box(), "by meaning{Enter}");
    expect(await screen.findByText("Meaning search")).toBeInTheDocument();
    expect(screen.getByText("similarity 0.69")).toBeInTheDocument();
    expect(screen.getByText(/retrieved by meaning search/)).toBeInTheDocument();

    vi.mocked(api.askQuestion).mockResolvedValueOnce(response("tfidf"));
    await userEvent.click(screen.getByRole("radio", { name: "Keyword" }));
    await userEvent.type(box(), "by keyword{Enter}");
    expect(await screen.findByText("Keyword search")).toBeInTheDocument();
    expect(screen.getByText("match 0.69")).toBeInTheDocument();
    expect(screen.getByText(/retrieved by keyword matching/)).toBeInTheDocument();
  });

  it("shows the server's notice about documents that are not indexed for meaning search", async () => {
    setup(true);
    await ready();
    vi.mocked(api.askQuestion).mockResolvedValue(response("embedding", "1 of 2 document(s) are not indexed for meaning search."));
    await userEvent.click(await screen.findByRole("radio", { name: "Meaning" }));
    await userEvent.type(box(), "anything here{Enter}");
    expect(await screen.findByText(/not indexed for meaning search/)).toBeInTheDocument();
  });
});
