// Mirrors the API responses (apps/api/app/main.py). Keep in sync by hand for now.
export type DocumentSummary = {
  id: string;
  name: string;
  size_bytes: number;
  page_count: number;
  chunk_count: number;
  status: string;
  has_file: boolean; // whether the original file is stored (older documents have none)
  semantic: boolean; // whether meaning search covers this document
};

export type Health = {
  status: string;
  version: string;
  environment: string;
  generation_available: boolean;
  meaning_search_available: boolean;
};

export type AnswerMode = "sources_only" | "generated";
export type Retrieval = "tfidf" | "embedding"; // keyword matching or meaning search

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
  retrieval: Retrieval; // which method found the evidence: scores are not comparable across methods
  request_id: string;
  notice: string | null;
};

export type ViewLink = {
  url: string; // a short-lived bearer link: never store or log it
  expires_in: number;
  page: number | null;
  filename: string;
};

// ---- Published retrieval evaluation (GET /api/v1/evaluation/latest), measured results only ----
export type Stat = { value: number | null; ci: [number, number] | null; n: number };

export type OperatingPoint = {
  thresholds: Record<string, number>;
  abstention_accuracy_on_unanswerable: Stat;
  false_abstain_rate_on_answerable: Stat;
  "end_to_end_recall@3": Stat;
};

export type MethodResult = {
  label: string;
  ranking: Record<"recall@1" | "recall@3" | "recall@5" | "mrr", Stat>;
  ranking_by_type: Record<string, { n: number; "recall@3": Stat; mrr: Stat }>;
  operating_point_tuned: OperatingPoint | null;
  operating_point_at_product_defaults: OperatingPoint | null;
  balanced_accuracy_tuned: number | null;
  latency_ms: { median: number | null; p95: number | null };
};

export type EvaluationResults = {
  run: {
    split: string;
    date: string;
    git: { commit: string | null; dirty: boolean };
    questions: { total: number; answerable: number; unanswerable: number };
    chunks: number;
    chunk_size: number;
    overlap: number;
    embedding_model: string;
  };
  thresholds: { tuned: { tfidf: number; embedding: number }; product_defaults: { tfidf: number; embedding: number }; tuned_on: string };
  caveats: string[];
  methods: Record<string, MethodResult>;
  product_keyword_latency_ms: { median: number | null; p95: number | null };
  chunk_experiment: { split: string; chosen: number; rows: Record<string, { chunks: number; tfidf: Record<string, Stat>; embedding: Record<string, Stat> }> };
  recommendation: { text: string };
  analysis: {
    note: string;
    patterns: { title: string; evidence: string; example_ids: string[] }[];
    label_limitations: { id: string; explanation: string }[];
    misses: { id: string; category: string; ranks: Record<string, number>; explanation: string }[];
  };
  not_measured: string[];
};
