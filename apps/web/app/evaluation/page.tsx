export default function EvaluationPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-3xl font-black sm:text-4xl">Retrieval evaluation</h1>
      <p className="mt-1 text-muted">Compare keyword search and embedding retrieval on a labeled question set.</p>
      <div className="mt-8 rounded-2xl border border-dashed border-line bg-panel px-8 py-12 text-center">
        <p className="text-lg font-bold">No evaluation has been run yet</p>
        <p className="mx-auto mt-2 max-w-lg text-muted">
          This page will show measured Recall@k, MRR and abstention accuracy once a labeled question set exists. Until then there are
          no numbers here, on purpose: only real, reproducible results will be displayed.
        </p>
      </div>
    </div>
  );
}
