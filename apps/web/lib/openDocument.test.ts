import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getViewLink = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getViewLink: (...args: unknown[]) => getViewLink(...args) };
});

import { ApiError } from "./api";
import { openDocumentPage, openErrorMessage } from "./openDocument";

const LINK = "https://proj.supabase.co/storage/v1/object/sign/documents/u/d?token=abc";
let tab: { opener: unknown; location: { replace: ReturnType<typeof vi.fn> }; close: ReturnType<typeof vi.fn> };
let openSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  tab = { opener: "the-app-window", location: { replace: vi.fn() }, close: vi.fn() };
  openSpy = vi.fn(() => tab);
  vi.stubGlobal("open", openSpy);
  window.open = openSpy as unknown as typeof window.open;
  getViewLink.mockResolvedValue({ url: LINK, expires_in: 60, page: 2, filename: "paper.pdf" });
});
afterEach(() => {
  vi.unstubAllGlobals();
  getViewLink.mockReset();
});

describe("openDocumentPage", () => {
  it("opens the tab before the network call, so the pop-up blocker allows it", async () => {
    let tabOpenedBeforeRequest = false;
    getViewLink.mockImplementation(async () => {
      tabOpenedBeforeRequest = openSpy.mock.calls.length === 1;
      return { url: LINK, expires_in: 60, page: 2, filename: "paper.pdf" };
    });
    await openDocumentPage("doc-1", 2);
    expect(tabOpenedBeforeRequest).toBe(true);
    expect(openSpy).toHaveBeenCalledWith("about:blank", "_blank");
  });

  it("cuts the new page off from this one", async () => {
    await openDocumentPage("doc-1", 2);
    expect(tab.opener).toBeNull();
  });

  it("jumps to the page in a PDF with a fragment that never reaches a server", async () => {
    await openDocumentPage("doc-1", 2);
    expect(getViewLink).toHaveBeenCalledWith("doc-1", 2);
    expect(tab.location.replace).toHaveBeenCalledWith(`${LINK}#page=2`);
  });

  it("does not add a page fragment for text files or when no page is given", async () => {
    getViewLink.mockResolvedValue({ url: LINK, expires_in: 60, page: 1, filename: "notes.txt" });
    await openDocumentPage("doc-1", 1);
    expect(tab.location.replace).toHaveBeenLastCalledWith(LINK);
    getViewLink.mockResolvedValue({ url: LINK, expires_in: 60, page: null, filename: "paper.pdf" });
    await openDocumentPage("doc-1");
    expect(tab.location.replace).toHaveBeenLastCalledWith(LINK);
  });

  it("closes the blank tab and reports the problem when no link can be issued", async () => {
    getViewLink.mockRejectedValue(new ApiError(404, "The original file isn't stored for this document."));
    await expect(openDocumentPage("doc-1", 1)).rejects.toMatchObject({ status: 404 });
    expect(tab.close).toHaveBeenCalled();
    expect(tab.location.replace).not.toHaveBeenCalled();
  });

  it("explains a blocked pop-up and never requests a link it cannot use", async () => {
    openSpy.mockReturnValue(null);
    await expect(openDocumentPage("doc-1", 1)).rejects.toThrow(/blocked the new tab/);
    expect(getViewLink).not.toHaveBeenCalled();
  });
});

describe("openErrorMessage", () => {
  it("shows API messages and hides anything unexpected", () => {
    expect(openErrorMessage(new ApiError(404, "Not stored"))).toBe("Not stored");
    expect(openErrorMessage(new Error("stack trace with secrets"))).toBe("Could not open the file.");
  });
});
