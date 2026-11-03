import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const openDocumentPage = vi.fn();
vi.mock("@/lib/openDocument", async () => {
  const actual = await vi.importActual<typeof import("@/lib/openDocument")>("@/lib/openDocument");
  return { ...actual, openDocumentPage: (...a: unknown[]) => openDocumentPage(...a) };
});

const documents = [
  { id: "d1", name: "stored.pdf", size_bytes: 10, page_count: 2, chunk_count: 2, status: "ready", has_file: true, semantic: true },
  { id: "d2", name: "legacy.pdf", size_bytes: 10, page_count: 1, chunk_count: 1, status: "ready", has_file: false, semantic: false },
];
vi.mock("./DocumentsProvider", () => ({
  useDocuments: () => ({ documents, loaded: true, apiError: null, uploads: [], removeDocument: vi.fn(), dismissUpload: vi.fn() }),
}));

import { DocumentList } from "./DocumentList";

beforeEach(() => openDocumentPage.mockReset().mockResolvedValue(undefined));

describe("Meaning-search coverage", () => {
  it("flags documents that only support keyword search", () => {
    render(<DocumentList />);
    expect(screen.getAllByText("Keyword only")).toHaveLength(1);              // legacy.pdf only
    expect(screen.getByText("Keyword only")).toHaveAttribute("title", expect.stringContaining("Upload it again"));
  });
});

describe("Open a stored document", () => {
  it("offers Open only for documents whose original file is stored", () => {
    render(<DocumentList />);
    expect(screen.getByRole("button", { name: "Open stored.pdf in a new tab" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open legacy.pdf in a new tab" })).toBeNull();
    expect(screen.getByText("File not stored")).toBeInTheDocument();
  });

  it("opens the whole document (no page) when asked", async () => {
    render(<DocumentList />);
    await userEvent.click(screen.getByRole("button", { name: "Open stored.pdf in a new tab" }));
    expect(openDocumentPage).toHaveBeenCalledWith("d1");
  });
});
