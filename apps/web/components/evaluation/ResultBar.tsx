import { fmtStat } from "@/lib/evaluation";
import type { Stat } from "@/lib/types";

/**
 * A value as a bar, with its 95% interval as a whisker. The bar is decoration: the number and the
 * interval are always written out, so nothing depends on seeing the picture.
 */
export function ResultBar({ stat }: { stat: Stat | null | undefined }) {
  if (!stat || stat.value === null) return <span className="text-muted">n/a</span>;
  const value = stat.value;
  const pct = (x: number) => `${Math.max(0, Math.min(1, x)) * 100}%`;
  return (
    <div className="min-w-28 sm-metric">
      <span className="text-[12px] font-bold text-text">{fmtStat(stat)}</span>
      <div aria-hidden className="relative mt-2 h-1.5 overflow-hidden rounded-full bg-[#e9ecf6] dark:bg-[#353247]">
        <div className="absolute inset-y-0 left-0 rounded-full bg-[#6366f1]" style={{ width: pct(value) }} />
        {stat.ci && (
          <div
            className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-[#31406c]/80"
            style={{ left: pct(stat.ci[0]), width: `${Math.max(0, Math.min(1, stat.ci[1]) - Math.max(0, stat.ci[0])) * 100}%` }}
          />
        )}
      </div>
    </div>
  );
}
