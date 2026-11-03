import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAccessToken = vi.fn();
vi.mock("@/lib/supabase", () => ({ getAccessToken: () => getAccessToken(), supabase: null, isConfigured: true }));

import { ApiError, askQuestion, deleteDocument, getHealth, listDocuments, setUnauthorizedHandler, uploadDocument } from "./api";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => json(200, { documents: [] }));
  vi.stubGlobal("fetch", fetchMock);
  getAccessToken.mockResolvedValue("jwt-123");
});
afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
  getAccessToken.mockReset();
});

const headersOfCall = (n = 0) => new Headers((fetchMock.mock.calls[n][1] as RequestInit).headers);

describe("api client authentication", () => {
  it("sends the current access token on every protected call", async () => {
    await listDocuments();
    await deleteDocument("abc");
    await askQuestion("what is this?", "sources_only", "tfidf");
    await uploadDocument(new File(["x"], "a.txt"));
    for (let i = 0; i < 4; i++) expect(headersOfCall(i).get("Authorization")).toBe("Bearer jwt-123");
  });

  it("does not send a token to the public health endpoint", async () => {
    fetchMock.mockResolvedValue(json(200, { status: "ok" }));
    await getHealth();
    expect(headersOfCall().get("Authorization")).toBeNull();
  });

  it("asks for a fresh token on each call, so refreshed tokens are used", async () => {
    await listDocuments();
    getAccessToken.mockResolvedValue("jwt-456");
    await listDocuments();
    expect(headersOfCall(1).get("Authorization")).toBe("Bearer jwt-456");
  });

  it("refuses to call the API at all when signed out", async () => {
    getAccessToken.mockResolvedValue(null);
    await expect(listDocuments()).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the JSON content type for questions and lets uploads set their own", async () => {
    await askQuestion("what is this?", "sources_only", "tfidf");
    expect(headersOfCall(0).get("Content-Type")).toBe("application/json");
    await uploadDocument(new File(["x"], "a.txt"));
    expect(headersOfCall(1).get("Content-Type")).toBeNull(); // the browser adds the multipart boundary
  });

  it("calls the unauthorized handler when the API rejects the token", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(json(401, { detail: "Not authenticated" }));
    await expect(listDocuments()).rejects.toBeInstanceOf(ApiError);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not treat other errors as a lost session", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(json(409, { detail: "Document limit reached" }));
    await expect(listDocuments()).rejects.toMatchObject({ status: 409 });
    fetchMock.mockResolvedValue(json(502, { detail: "Storage is unavailable" }));
    await expect(listDocuments()).rejects.toMatchObject({ status: 502 });
    expect(handler).not.toHaveBeenCalled();
  });

  it("never puts the token in the URL", async () => {
    await listDocuments();
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("jwt-123");
  });
});
