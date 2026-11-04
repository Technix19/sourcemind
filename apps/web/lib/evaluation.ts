import type { Stat } from "./types";

/** "0.87" or "n/a" */
export function fmtValue(stat: Stat | null | undefined): string {
  return stat && stat.value !== null ? stat.value.toFixed(2) : "n/a";
}

/** "0.67 to 1.00": the 95% interval, spelled so a screen reader reads it sensibly. */
export function fmtRange(stat: Stat | null | undefined): string {
  return stat && stat.ci ? `${stat.ci[0].toFixed(2)} to ${stat.ci[1].toFixed(2)}` : "";
}

export function fmtStat(stat: Stat | null | undefined): string {
  const range = fmtRange(stat);
  return range ? `${fmtValue(stat)} (${range})` : fmtValue(stat);
}

export const TYPE_LABELS: Record<string, string> = {
  direct: "Direct (same words)",
  paraphrase: "Paraphrase (different words)",
  specific: "Specific fact",
};

export const CATEGORY_LABELS: Record<string, string> = {
  label_gap: "label gap",
  adjacent_topic: "adjacent topic",
  vocabulary_gap: "vocabulary gap",
};
