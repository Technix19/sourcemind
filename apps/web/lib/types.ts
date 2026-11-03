// Mirrors the API responses (apps/api/app/main.py). Keep in sync by hand for now.
export type DocumentSummary = {
  id: string;
  name: string;
  size_bytes: number;
  page_count: number;
  chunk_count: number;
  status: string;
  has_file: boolean; // whether the original file is stored (older documents have none)
};

export type Health = {
  status: string;
  version: string;
  environment: string;
  generation_available: boolean;
};

export type AnswerMode = "sources_only" | "generated";

export type Evidence = {
  citation_id: string; // "1", "2", ... the same numbers the answer's [n] markers use
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number;
  excerpt: string;
  score: number; // lexical similarity, NOT a probability that the answer is correct
};

export type QueryResponse = {
  answer_mode: AnswerMode;
  answer: string | null;
  insufficient_evidence: boolean;
  evidence: Evidence[];
  model_used: string | null;
  request_id: string;
  notice: string | null;
};

export type ViewLink = {
  url: string; // a short-lived bearer link: never store or log it
  expires_in: number;
  page: number | null;
  filename: string;
};
