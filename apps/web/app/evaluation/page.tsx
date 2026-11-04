"use client";

import { useEffect, useState } from "react";
import { EvaluationReport } from "@/components/evaluation/EvaluationReport";
import { ApiError, getEvaluation } from "@/lib/api";
import type { EvaluationResults } from "@/lib/types";

type State = { status: "loading" } | { status: "missing" } | { status: "error"; message: string } | { status: "ready"; results: EvaluationResults };

export default function EvaluationPage() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getEvaluation()
      .then((results) => !cancelled && setState({ status: "ready", results }))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setState({ status: "missing" });
        else setState({ status: "error", message: err instanceof ApiError ? err.message : "Could not load the evaluation results." });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "ready") return <EvaluationReport results={state.results} />;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-3xl font-black sm:text-4xl">Retrieval evaluation</h1>
      <p className="mt-1 text-muted">Compare keyword search and meaning search on a labeled question set.</p>
      <div role={state.status === "error" ? "alert" : "status"} className="mt-8 rounded-2xl border border-dashed border-line bg-panel px-8 py-12 text-center">
        {state.status === "loading" && <p className="text-muted">Loading results…</p>}
        {state.status === "missing" && (
          <>
            <p className="text-lg font-bold">No evaluation has been published yet</p>
            <p className="mx-auto mt-2 max-w-lg text-muted">
              This page only shows measured, reproducible results. Run the evaluation and publish it (see <code>data/evaluation/README.md</code>) and it will appear here.
            </p>
          </>
        )}
        {state.status === "error" && <p className="text-danger">{state.message}</p>}
      </div>
    </div>
  );
}
