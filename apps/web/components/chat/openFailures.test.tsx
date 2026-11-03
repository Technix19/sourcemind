// Failure paths for "Open page" / "Open", run through the REAL openDocumentPage and api client
// with only fetch and window.open stubbed (see page.errors.test.tsx for why not a rejecting mock).
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase", () => ({ getAccessToken: async () => "test-token", supabase: null, isConfigured: true }));
vi.mock("./ChatProvider", () => ({
  useChat: () => ({
    selection: null,
    activeTurn: {
      id: 1, question: "q", mode: "sources_only", status: "done",
      response: {
        answer_mode: "sources_only", answer: null, insufficient_evidence: false, model_used: null, retrieval: "tfidf", request_id: "r", notice: null,
        evidence: [{ citation_id: "1", chunk_id: "c1", document_id: "doc-9", filename: "paper.pdf", page_number: 3, excerpt: "text", score: 0.4 }],
      },
    },
  }),
}));
const documents = [{ id: "d1", name: "stored.pdf", size_bytes: 10, page_count: 2, chunk_count: 2, status: "ready", has_file: true, semantic: true }];
vi.mock("@/components/documents/DocumentsProvider", () => ({
  useDocuments: () => ({ documents, loaded: true, apiError: null, uploads: [], removeDocument: vi.fn(), dismissUpload: vi.fn() }),
}));

import { DocumentList } from "@/components/documents/DocumentList";
import { EvidencePanel } from "./EvidencePanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
let tab: { opener: unknown; location: { replace: ReturnType<typeof vi.fn> }; close: ReturnType<typeof vi.fn> };

beforeEach(() => {
  tab = { opener: "app", location: { replace: vi.fn() }, close: vi.fn() };
  window.open = vi.fn(() => tab) as unknown as typeof window.open;
});
afterEach(() => vi.unstubAllGlobals());

describe("opening the original file", () => {
  it("evidence card: shows the API's reason, closes the blank tab, and stays usable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(404, { detail: "The original file isn't stored for this document. Upload it again to enable this." })));
    render(<EvidencePanel />);
    await userEvent.click(screen.getByRole("button", { name: "Open page 3 of paper.pdf in a new tab" }));
    expect(await screen.findByText(/Upload it again to enable this/)).toBeInTheDocument();
    expect(tab.close).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Open page 3 of paper.pdf in a new tab" })).toBeEnabled();
  });

  it("evidence card: on success, goes to the signed link at the cited page", async () => {
    const link = "https://proj.supabase.co/storage/v1/object/sign/documents/u/doc-9?token=abc";
    const fetchMock = vi.fn<typeof fetch>(async () => json(200, { url: link, expires_in: 60, page: 3, filename: "paper.pdf" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<EvidencePanel />);
    await userEvent.click(screen.getByRole("button", { name: "Open page 3 of paper.pdf in a new tab" }));
    await vi.waitFor(() => expect(tab.location.replace).toHaveBeenCalledWith(`${link}#page=3`));
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/documents\/doc-9\/view\?page=3$/);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer test-token");
  });

  it("document list: a failure is explained next to the document without leaking details", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(502, { detail: "Storage is unavailable right now. Try again shortly." })));
    render(<DocumentList />);
    await userEvent.click(screen.getByRole("button", { name: "Open stored.pdf in a new tab" }));
    expect(await screen.findByText("Storage is unavailable right now. Try again shortly.")).toBeInTheDocument();
  });

  it("a blocked pop-up is explained and no link is requested", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    window.open = vi.fn(() => null) as unknown as typeof window.open;
    render(<DocumentList />);
    await userEvent.click(screen.getByRole("button", { name: "Open stored.pdf in a new tab" }));
    expect(await screen.findByText(/blocked the new tab/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
