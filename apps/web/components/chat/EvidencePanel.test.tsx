import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const openDocumentPage = vi.fn();
vi.mock("@/lib/openDocument", async () => {
  const actual = await vi.importActual<typeof import("@/lib/openDocument")>("@/lib/openDocument");
  return { ...actual, openDocumentPage: (...a: unknown[]) => openDocumentPage(...a) };
});
vi.mock("./ChatProvider", () => ({
  useChat: () => ({
    selection: null,
    activeTurn: {
      id: 1, question: "q", mode: "sources_only", status: "done",
      response: {
        answer_mode: "sources_only", answer: null, insufficient_evidence: false, model_used: null, request_id: "r", notice: null,
        evidence: [{ citation_id: "1", chunk_id: "c1", document_id: "doc-9", filename: "paper.pdf", page_number: 3, excerpt: "text", score: 0.4 }],
      },
    },
  }),
}));

import { EvidencePanel } from "./EvidencePanel";

beforeEach(() => openDocumentPage.mockReset().mockResolvedValue(undefined));

describe("Open page", () => {
  const button = () => screen.getByRole("button", { name: "Open page 3 of paper.pdf in a new tab" });

  it("opens the cited document at the cited page", async () => {
    render(<EvidencePanel />);
    await userEvent.click(button());
    expect(openDocumentPage).toHaveBeenCalledWith("doc-9", 3);
  });

  it("works from the keyboard", async () => {
    render(<EvidencePanel />);
    button().focus();
    await userEvent.keyboard("{Enter}");
    expect(openDocumentPage).toHaveBeenCalledTimes(1);
  });

  it("ignores a second click while the first is still opening", async () => {
    let finish!: () => void;
    openDocumentPage.mockReturnValue(new Promise<void>((r) => (finish = r)));
    render(<EvidencePanel />);
    await userEvent.click(button());
    expect(screen.getByRole("button", { name: /Open page 3 of paper.pdf/ })).toBeDisabled();
    expect(screen.getByText("Opening…")).toBeInTheDocument();
    finish();
    await waitFor(() => expect(screen.getByText("Open page →")).toBeInTheDocument());
    expect(openDocumentPage).toHaveBeenCalledTimes(1);
  });
});
