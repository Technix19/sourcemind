import { CATEGORY_LABELS, TYPE_LABELS, fmtStat } from "@/lib/evaluation";
import type { EvaluationResults, OperatingPoint } from "@/lib/types";
import { ResultBar } from "./ResultBar";

const th = "bg-[#fafbfe] px-4 py-3 text-left text-[11px] font-bold text-muted";
const td = "px-4 py-3.5 align-top text-[12px]";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-12 border-t border-line pt-8">
      <h2 className="mb-3 text-xl font-black tracking-[-.02em]">{title}</h2>
      {children}
    </section>
  );
}

function Table({ caption, children }: { caption: string; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-[0_1px_2px_rgba(15,23,42,0.025)]">
      <table className="w-full min-w-[40rem] border-collapse text-[12px]">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

function OperatingRow({ label, name, point }: { label: string; name: string; point: OperatingPoint | null }) {
  if (!point) return null;
  return (
    <tr className="border-t border-line">
      <th scope="row" className={`${td} font-bold`}>
        {name}
      </th>
      <td className={td}>{label}</td>
      <td className={td}>{fmtStat(point.abstention_accuracy_on_unanswerable)}</td>
      <td className={td}>{fmtStat(point.false_abstain_rate_on_answerable)}</td>
      <td className={td}>{fmtStat(point["end_to_end_recall@3"])}</td>
    </tr>
  );
}

/** Renders ONLY what the evaluation measured. Every number comes from the published results file. */
export function EvaluationReport({ results }: { results: EvaluationResults }) {
  const { run, methods } = results;
  const entries = Object.entries(methods);
  const types = Array.from(new Set(entries.flatMap(([, m]) => Object.keys(m.ranking_by_type)))).sort();
  const commit = run.git.commit ?? "unknown";

  return (
    <div className="mx-auto max-w-[1300px]">
      <h1 className="sm-page-title">Retrieval evaluation</h1>
      <p className="mt-2 text-sm text-muted">How reliably each search method finds the right page, measured on a held-out question set.</p>
      <div className="mt-5 flex flex-wrap gap-2 text-[12px]">
        <span className="rounded-md border border-line bg-white px-3 py-2 text-muted"><strong className="sm-metric text-text">{run.questions.total}</strong> questions</span>
        <span className="rounded-md border border-line bg-white px-3 py-2 text-muted"><strong className="sm-metric text-text">{run.questions.answerable}</strong> answerable</span>
        <span className="rounded-md border border-line bg-white px-3 py-2 text-muted"><strong className="sm-metric text-text">{run.questions.unanswerable}</strong> unanswerable</span>
        <span className="rounded-md border border-line bg-white px-3 py-2 text-muted"><strong className="sm-metric text-text">{run.chunks.toLocaleString()}</strong> chunks</span>
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-muted">
        Held-out <strong className="text-text">{run.split}</strong> split · scored once on {run.date} at commit <code>{commit}</code>
        {run.git.dirty ? " (uncommitted changes)" : ""} · {run.questions.total} questions ({run.questions.answerable} answerable,{" "}
        {run.questions.unanswerable} unanswerable) · {run.chunks.toLocaleString()} chunks of {run.chunk_size} characters
      </p>

      <aside aria-labelledby="read-first" className="mt-5 rounded-xl border border-[#eadcc2] bg-[#fffdf8] px-4 py-4">
        <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
          <h2 id="read-first" className="shrink-0 text-[13px] font-bold text-[#78510f]">Read this first</h2>
          <p className="flex-1 text-[12px] leading-relaxed text-[#78510f]">
            A small held-out test set. Results measure retrieval, not the correctness of generated answers.
          </p>
        </div>
        <details className="mt-2 text-[12px]">
          <summary className="w-fit cursor-pointer rounded font-bold text-[#78510f] hover:underline">Methodology and limitations</summary>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 leading-relaxed text-[#78510f]">
            {results.caveats.map((c) => <li key={c}>{c}</li>)}
          </ul>
          <p className="mt-3 leading-relaxed text-[#78510f]">Values are means with 95% bootstrap intervals. If two intervals overlap, no difference is demonstrated.</p>
        </details>
        <p className="mt-2 text-[11px] text-[#8d743c]">Values are means with 95% bootstrap intervals; interpret comparisons cautiously.</p>
      </aside>

      <Section title="Ranking quality">
        <p className="mb-3 text-sm text-muted">Recall@k: the share of answerable questions where a correct page is among the top k results. MRR rewards finding it earlier.</p>
        <Table caption="Ranking quality by search method, with 95% intervals">
          <thead>
            <tr>
              <th scope="col" className={th}>Method</th>
              <th scope="col" className={th}>Recall@1</th>
              <th scope="col" className={th}>Recall@3</th>
              <th scope="col" className={th}>Recall@5</th>
              <th scope="col" className={th}>MRR</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, m]) => (
              <tr key={key} className="border-t border-line hover:bg-[#fafbff]">
                <th scope="row" className={`${td} font-bold`}>{m.label}</th>
                <td className={td}><ResultBar stat={m.ranking["recall@1"]} /></td>
                <td className={td}><ResultBar stat={m.ranking["recall@3"]} /></td>
                <td className={td}><ResultBar stat={m.ranking["recall@5"]} /></td>
                <td className={td}><ResultBar stat={m.ranking.mrr} /></td>
              </tr>
            ))}
          </tbody>
        </Table>

        <h3 className="mt-6 mb-2 font-bold">Recall@3 by question type</h3>
        <Table caption="Recall at 3 by question type and search method">
          <thead>
            <tr>
              <th scope="col" className={th}>Question type</th>
              {entries.map(([key, m]) => (
                <th key={key} scope="col" className={th}>{m.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((t) => (
              <tr key={t} className="border-t border-line hover:bg-[#fafbff]">
                <th scope="row" className={`${td} font-bold`}>
                  {TYPE_LABELS[t] ?? t} <span className="font-normal text-muted">(n={entries[0][1].ranking_by_type[t]?.n})</span>
                </th>
                {entries.map(([key, m]) => (
                  <td key={key} className={td}>{fmtStat(m.ranking_by_type[t]?.["recall@3"])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Saying “not enough evidence”">
        <p className="mb-3 text-sm text-muted">
          A relevance threshold decides when a method returns nothing. Thresholds were tuned on the development split (keyword {results.thresholds.tuned.tfidf}, meaning{" "}
          {results.thresholds.tuned.embedding}); the product&apos;s current defaults are {results.thresholds.product_defaults.tfidf} and {results.thresholds.product_defaults.embedding}. Only{" "}
          {run.questions.unanswerable} unanswerable test questions exist, so these intervals are very wide.
        </p>
        <Table caption="Abstention behavior at the tuned thresholds and at the product defaults">
          <thead>
            <tr>
              <th scope="col" className={th}>Method</th>
              <th scope="col" className={th}>Setting</th>
              <th scope="col" className={th}>Correct abstention</th>
              <th scope="col" className={th}>False abstention</th>
              <th scope="col" className={th}>End-to-end Recall@3</th>
            </tr>
          </thead>
          <tbody>
            {entries.flatMap(([key, m]) => [
              <OperatingRow key={`${key}-t`} name={m.label} label="tuned" point={m.operating_point_tuned} />,
              <OperatingRow key={`${key}-d`} name={m.label} label="product defaults" point={m.operating_point_at_product_defaults} />,
            ])}
          </tbody>
        </Table>
        <p className="mt-2 text-xs text-muted">Correct abstention: unanswerable questions that got no evidence. False abstention: answerable questions that were refused.</p>
      </Section>

      <Section title="Recommendation">
        <p className="rounded-xl border border-[#dadff9] bg-[#f3f5ff] px-5 py-4 text-[13px] leading-relaxed text-[#293566]">{results.recommendation.text}</p>
      </Section>

      <Section title="Speed">
        <p className="text-sm text-muted">
          Median search time on this machine, excluding network and database: keyword {fmtMs(methods.tfidf?.latency_ms.median)} (query only; the product refits keyword
          search per query, about {fmtMs(results.product_keyword_latency_ms.median)}), meaning {fmtMs(methods.embedding?.latency_ms.median)}.
        </p>
      </Section>

      <Section title="Chunk size (development split)">
        <Table caption="Recall at 3 for different chunk sizes on the development split">
          <thead>
            <tr>
              <th scope="col" className={th}>Size / overlap</th>
              <th scope="col" className={th}>Chunks</th>
              <th scope="col" className={th}>Keyword Recall@3</th>
              <th scope="col" className={th}>Meaning Recall@3</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(results.chunk_experiment.rows).map(([key, row]) => (
              <tr key={key} className="border-t border-line">
                <th scope="row" className={`${td} font-bold`}>{key}</th>
                <td className={td}>{row.chunks.toLocaleString()}</td>
                <td className={td}>{fmtStat(row.tfidf["recall@3"])}</td>
                <td className={td}>{fmtStat(row.embedding["recall@3"])}</td>
              </tr>
            ))}
          </tbody>
        </Table>
        <p className="mt-2 text-xs text-muted">The pre-registered rule keeps {results.chunk_experiment.chosen} characters unless another size wins on both Recall@3 and MRR by at least 0.10. None did.</p>
      </Section>

      <Section title="Failure analysis">
        <p className="mb-4 text-sm text-muted">{results.analysis.note}</p>
        <div className="grid gap-3 lg:grid-cols-2">
          {results.analysis.patterns.map((p) => (
            <article key={p.title} className="rounded-xl border border-line bg-white p-5">
              <h3 className="font-bold">{p.title}</h3>
              <p className="mt-2 text-sm text-muted">{p.evidence}</p>
            </article>
          ))}
        </div>

        <h3 className="mt-8 mb-2 font-bold">Limitations of the labels</h3>
        <ul className="space-y-3">
          {results.analysis.label_limitations.map((l) => (
            <li key={l.id} className="rounded-lg border border-line bg-white p-4 text-[13px]">
              <strong>{l.id}</strong>: {l.explanation}
            </li>
          ))}
        </ul>

        <h3 className="mt-8 mb-2 font-bold">Individual misses</h3>
        <p className="mb-3 text-sm text-muted">Rank of the first correct page, by method (1 is best).</p>
        <ul className="space-y-3">
          {results.analysis.misses.map((x) => (
            <li key={x.id} className="rounded-xl border border-line bg-panel p-4 text-sm">
              <p>
                <strong>{x.id}</strong> · {CATEGORY_LABELS[x.category] ?? x.category} ·{" "}
                {Object.entries(x.ranks).map(([k, v]) => `${k} ${v}`).join(", ")}
              </p>
              <p className="mt-1 text-muted">{x.explanation}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Not measured">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted">
          {results.not_measured.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
        <p className="mt-6 text-xs text-muted">
          Reproduce with <code>python -m evaluation.run</code> (see <code>data/evaluation/README.md</code>). Full report: <code>data/evaluation/results/REPORT.md</code>.
        </p>
      </Section>
    </div>
  );
}

function fmtMs(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : `${value.toFixed(value < 10 ? 1 : 0)} ms`;
}
