# Generated-answer evaluation

Run on 2026-11-05 at commit `47e9d10`. Model `claude-haiku-5-5`, effort `low`, 45 questions x 3 runs, keyword retrieval (top 4, minimum score 0.05). Plan: `docs/m8-generation-eval.md`, written before the run.

Values are means with 95% bootstrap intervals over questions. **This checks that cited pages contain the labeled answer, not that the answer text is true.** Small sample, one author, one model.

| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Answer rate (evidence available) | 1.00 (1.00 to 1.00), n=22 | 1.00 (1.00 to 1.00), n=22 | 1.00 (1.00 to 1.00), n=22 |
| Supported-citation rate (of answered) | 1.00 (1.00 to 1.00), n=22 | 1.00 (1.00 to 1.00), n=22 | 1.00 (1.00 to 1.00), n=22 |
| Wrong abstention (evidence available) | 0.00 (0.00 to 0.00), n=22 | 0.00 (0.00 to 0.00), n=22 | 0.00 (0.00 to 0.00), n=22 |
| Answered although no relevant page was retrieved | 0.82 (0.55 to 1.00), n=11 | 0.82 (0.55 to 1.00), n=11 | 0.64 (0.36 to 0.91), n=11 |
| Invented answer on an unanswerable question | 0.67 (0.42 to 0.92), n=12 | 0.58 (0.33 to 0.83), n=12 | 0.58 (0.33 to 0.83), n=12 |
| Product abstained on unanswerable | 0.25 (0.00 to 0.50), n=12 | 0.33 (0.08 to 0.58), n=12 | 0.33 (0.08 to 0.58), n=12 |

## Outcomes per run

| Run | no_evidence | abstained | withheld | answered | error |
|---|---|---|---|---|---|
| 1 | 0 | 5 | 1 | 39 | 0 |
| 2 | 0 | 6 | 1 | 38 | 0 |
| 3 | 0 | 8 | 1 | 36 | 0 |

## Concerns (pre-registered lines)

- Answered an unanswerable question: csf-06
- Answered an unanswerable question: rmf-06
- Answered an unanswerable question: sleep-06
- Answered an unanswerable question: fed-06
- Answered an unanswerable question: con-06
- Answered an unanswerable question: off-02
- Answered an unanswerable question: x-05
- Answered an unanswerable question: x-10
- Answered an unanswerable question: off-03
- Answered an unanswerable question: off-01

Questions whose outcome changed between runs: `rmf-02` (abstained / answered / abstained), `rmf-06` (answered / answered / abstained), `sleep-06` (answered / abstained / answered), `fed-04` (answered / abstained / abstained), `off-01` (withheld / withheld / answered), `off-03` (abstained / answered / withheld), `x-04` (answered / answered / abstained), `x-10` (answered / abstained / abstained).

Latency per call (run 1): median 1486.6 ms, p95 4150.8 ms. Tokens used across all runs: 168,810 in, 35,367 out.
