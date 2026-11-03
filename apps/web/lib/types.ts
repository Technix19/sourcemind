// Mirrors the API responses (apps/api/app/main.py). Keep in sync by hand for now.
export type DocumentSummary = {
  id: string;
  name: string;
  size_bytes: number;
  page_count: number;
  chunk_count: number;
  status: string;
};

export type Health = {
  status: string;
  version: string;
  environment: string;
  generation_available: boolean;
};
