import fs from "node:fs";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvaluationResults, Stat } from "@/lib/types";
import { fmtStat } from "@/lib/evaluation";
import { EvaluationReport } from "./EvaluationReport";
import { ResultBar } from "./ResultBar";

const stat = (value: number, lo: number, hi: number, n = 10): Stat => ({ value, ci: [lo, hi], n });
const op = (correct: Stat, falseAbstain: Stat, e2e: Stat) => ({
  thresholds: { x: 0.5 },
  abstention_accuracy_on_unanswerable: correct,
  false_abstain_rate_on_answerable: falseAbstain,
  "end_to_end_recall@3": e2e,
});
const method = (label: string, r3: Stat) => ({
  label,
  ranking: { "recall@1": stat(0.4, 0.2, 0.6), "recall@3": r3, "recall@5": stat(0.9, 0.7, 1), mrr: stat(0.55, 0.35, 0.75) },
  ranking_by_type: { paraphrase: { n: 7, "recall@3": stat(0.43, 0.14, 0.86), mrr: stat(0.3, 0.1, 0.5) } },
  operating_point_tuned: op(stat(1, 1, 1, 4), stat(0.67, 0.4, 0.87), stat(0.33, 0.13, 0.6)),
  operating_point_at_product_defaults: op(stat(0, 0, 0, 4), stat(0, 0, 0), stat(0.6, 0.33, 0.8)),
  balanced_accuracy_tuned: 0.66,
  latency_ms: { median: 1.1, p95: 2 },
});

const RESULTS: EvaluationResults = {
  run: { split: "test", date: "2026-11-04", git: { commit: "abc1234", dirty: false }, questions: { total: 19, answerable: 15, unanswerable: 4 }, chunks: 1345, chunk_size: 950, overlap: 170, embedding_model: "m" },
  thresholds: { tuned: { tfidf: 0.25, embedding: 0.7 }, product_defaults: { tfidf: 0.05, embedding: 0.5 }, tuned_on: "dev split" },
  caveats: ["Small sample: 15 answerable questions.", "A single author wrote all questions."],
  methods: { tfidf: method("Keyword (TF-IDF)", stat(0.6, 0.33, 0.8, 15)), embedding: method("Meaning (embeddings)", stat(0.87, 0.67, 1, 15)) },
  product_keyword_latency_ms: { median: 106.7, p95: 109.7 },
  chunk_experiment: { split: "dev", chosen: 950, rows: { "950/170": { chunks: 1345, tfidf: { "recall@3": stat(0.67, 0.44, 0.89) }, embedding: { "recall@3": stat(0.78, 0.56, 0.94) } } } },
  recommendation: { text: "No difference is demonstrated: the 95% intervals overlap." },
  analysis: {
    note: "Written AFTER the held-out test split was scored.",
    patterns: [{ title: "Keyword fails on paraphrases", evidence: "Recall@3 0.43 vs 0.86", example_ids: ["csf-03"] }],
    label_limitations: [{ id: "con-04", explanation: "Index pages restate the answer." }],
    misses: [{ id: "x-06", category: "adjacent_topic", ranks: { keyword: 4, meaning: 4 }, explanation: "Right topic, wrong passage." }],
  },
  not_measured: ["Citation accuracy of generated answers."],
};

describe("EvaluationReport", () => {
  it("states where the numbers come from: split, date, commit, sample size", () => {
    render(<EvaluationReport results={RESULTS} />);
    expect(screen.getByRole("heading", { level: 1, name: "Retrieval evaluation" })).toBeInTheDocument();
    expect(screen.getByText(/scored once on 2026-11-04 at commit/)).toBeInTheDocument();
    expect(screen.getByText("abc1234")).toBeInTheDocument();
    expect(screen.getByText(/19 questions \(15 answerable, 4 unanswerable\)/)).toBeInTheDocument();
  });

  it("puts the caveats above the numbers", () => {
    render(<EvaluationReport results={RESULTS} />);
    const notice = screen.getByRole("complementary", { name: "Read this first" });
    expect(within(notice).getByText("A single author wrote all questions.")).toBeInTheDocument();
    expect(within(notice).getByText(/If two intervals overlap, no difference is demonstrated/)).toBeInTheDocument();
    const position = (el: HTMLElement) => Array.from(document.body.querySelectorAll("*")).indexOf(el);
    expect(position(notice)).toBeLessThan(position(screen.getByRole("table", { name: /Ranking quality by search method/ })));
  });

  it("shows every ranking number with its interval, in an accessible table", () => {
    render(<EvaluationReport results={RESULTS} />);
    const table = screen.getByRole("table", { name: "Ranking quality by search method, with 95% intervals" });
    const keyword = within(table).getByRole("row", { name: /Keyword \(TF-IDF\)/ });
    expect(within(keyword).getByText("0.60 (0.33 to 0.80)")).toBeInTheDocument();
    const meaning = within(table).getByRole("row", { name: /Meaning \(embeddings\)/ });
    expect(within(meaning).getByText("0.87 (0.67 to 1.00)")).toBeInTheDocument();
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Method", "Recall@1", "Recall@3", "Recall@5", "MRR"]);
  });

  it("breaks results down by question type and shows both abstention settings", () => {
    render(<EvaluationReport results={RESULTS} />);
    const byType = screen.getByRole("table", { name: /by question type/ });
    expect(within(byType).getByRole("rowheader", { name: /Paraphrase \(different words\)/ })).toBeInTheDocument();
    const abstention = screen.getByRole("table", { name: /Abstention behavior/ });
    expect(within(abstention).getAllByText("tuned")).toHaveLength(2);
    expect(within(abstention).getAllByText("product defaults")).toHaveLength(2);
  });

  it("explains abstention numbers are fragile and never presents certainty", () => {
    render(<EvaluationReport results={RESULTS} />);
    expect(screen.getByText(/Only 4 unanswerable test questions exist, so these intervals are very wide/)).toBeInTheDocument();
  });

  it("shows the recommendation, chunk experiment, failure analysis and what was not measured", () => {
    render(<EvaluationReport results={RESULTS} />);
    expect(screen.getByText("No difference is demonstrated: the 95% intervals overlap.")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /different chunk sizes/ })).toBeInTheDocument();
    expect(screen.getByText("Keyword fails on paraphrases")).toBeInTheDocument();
    expect(screen.getByText(/Index pages restate the answer/)).toBeInTheDocument();
    expect(screen.getByText(/adjacent topic · keyword 4, meaning 4/)).toBeInTheDocument();
    expect(screen.getByText("Citation accuracy of generated answers.")).toBeInTheDocument();
  });

  it("never claims illustrative or placeholder numbers", () => {
    render(<EvaluationReport results={RESULTS} />);
    expect(document.body.textContent).not.toMatch(/illustrative|placeholder|sample data/i);
  });

  it("has a proper heading hierarchy (one h1, sections are h2)", () => {
    render(<EvaluationReport results={RESULTS} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(
      expect.arrayContaining(["Read this first", "Ranking quality", "Failure analysis", "Not measured"]),
    );
  });
});

describe("the real published results", () => {
  const file = path.resolve(__dirname, "../../../../data/evaluation/results/latest.json");
  const available = fs.existsSync(file);

  it.skipIf(!available)("render without errors and show exactly the numbers in the file", () => {
    const real = JSON.parse(fs.readFileSync(file, "utf8")) as EvaluationResults;
    render(<EvaluationReport results={real} />);
    const table = screen.getByRole("table", { name: /Ranking quality by search method/ });
    for (const m of Object.values(real.methods)) {
      const row = within(table).getByRole("row", { name: new RegExp(m.label.replace(/[()]/g, "\\$&")) });
      expect(within(row).getAllByText(fmtStat(m.ranking["recall@3"])).length).toBeGreaterThan(0);
      expect(within(row).getAllByText(fmtStat(m.ranking.mrr)).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(real.recommendation.text)).toBeInTheDocument();
    for (const miss of real.analysis.misses) expect(screen.getByText(miss.explanation)).toBeInTheDocument();
  });
});

describe("ResultBar", () => {
  it("writes the value and interval as text and hides the bar from assistive technology", () => {
    const { container } = render(<ResultBar stat={stat(0.5, 0.25, 0.75)} />);
    expect(screen.getByText("0.50 (0.25 to 0.75)")).toBeInTheDocument();
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("clamps out-of-range values instead of drawing outside the track", () => {
    const { container } = render(<ResultBar stat={stat(1.4, -0.2, 1.3)} />);
    const bars = container.querySelectorAll<HTMLElement>("[aria-hidden='true'] > div");
    expect(bars[0].style.width).toBe("100%");
    expect(bars[1].style.left).toBe("0%");
  });

  it("shows n/a instead of a bar when there is nothing to show", () => {
    render(<ResultBar stat={{ value: null, ci: null, n: 0 }} />);
    expect(screen.getByText("n/a")).toBeInTheDocument();
  });
});
