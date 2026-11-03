import { getAccessToken } from "./supabase";
import type { AnswerMode, DocumentSummary, Health, QueryResponse, ViewLink } from "./types";

// Public on purpose: it is only a URL. No secrets ever belong in the frontend.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Called when the API says our token is no longer valid (expired or revoked). The auth layer
// registers a handler that signs the user out and returns them to the login page.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init: RequestInit = {}, { auth = true } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const token = await getAccessToken();
    // No token means we are signed out: do not even send the request.
    if (!token) throw new ApiError(401, "Please sign in to continue.");
    headers.set("Authorization", `Bearer ${token}`);
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch (err) {
    // Let a user-initiated cancel through unchanged so callers can tell it from a failure.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, `Can't reach the API at ${API_URL}. Is it running?`);
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (auth && response.status === 401) onUnauthorized?.();
    // FastAPI sends {detail: "text"}; validation errors send a list, which we summarise.
    const detail = typeof body?.detail === "string" ? body.detail : "The request was not valid.";
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

// The only public endpoint: it needs no token.
export const getHealth = () => request<Health>("/api/v1/health", {}, { auth: false });

export const listDocuments = async () =>
  (await request<{ documents: DocumentSummary[] }>("/api/v1/documents")).documents;

export function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentSummary>("/api/v1/documents", { method: "POST", body: form });
}

export const deleteDocument = (id: string) =>
  request<void>(`/api/v1/documents/${encodeURIComponent(id)}`, { method: "DELETE" });

export const askQuestion = (question: string, mode: AnswerMode, signal?: AbortSignal) =>
  request<QueryResponse>("/api/v1/queries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode }),
    signal,
  });

export const getViewLink = (id: string, page?: number) =>
  request<ViewLink>(`/api/v1/documents/${encodeURIComponent(id)}/view${page ? `?page=${page}` : ""}`);
