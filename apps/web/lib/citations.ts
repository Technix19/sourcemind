export type Segment =
  | { type: "text"; text: string }
  | { type: "cite"; raw: string; numbers: string[] };

const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

/** Split an answer into plain text and [n] / [n, m] citation markers. Pure and string-only. */
export function splitCitations(answer: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of answer.matchAll(CITATION)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ type: "text", text: answer.slice(last, start) });
    segments.push({ type: "cite", raw: match[0], numbers: match[1].split(",").map((n) => n.trim()) });
    last = start + match[0].length;
  }
  if (last < answer.length) segments.push({ type: "text", text: answer.slice(last) });
  return segments;
}
