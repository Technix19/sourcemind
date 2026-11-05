import type { SVGProps } from "react";

/** Compact stacked-source mark: three passages becoming one searchable body of evidence. */
export function BrandMark({ size = 35, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      {...props}
    >
      <path d="M5 25.3 20 33l15-7.7v5.1L20 38 5 30.4v-5.1Z" fill="#312E81"/>
      <path d="M5 18.2 20 26l15-7.8v5.2L20 31 5 23.4v-5.2Z" fill="#4F46E5"/>
      <path d="M20 2 36.5 10.5v6L20 25 3.5 16.5v-6L20 2Z" fill="#6366F1"/>
      <path d="M20 2 36.5 10.5 20 19 3.5 10.5 20 2Z" fill="#818CF8"/>
      <path d="m20 19 16.5-8.5v6L20 25v-6Z" fill="#4338CA"/>
    </svg>
  );
}

export function BrandLogo({ tagline = false, compact = false }: { tagline?: boolean; compact?: boolean }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2.5">
      <BrandMark size={compact ? 30 : 38} className="shrink-0" />
      <span className="min-w-0 leading-none">
        <span className={"block whitespace-nowrap tracking-[-0.045em] text-text " + (compact ? "text-[17px] font-black" : "text-[22px] font-black")}>
          SourceMind
        </span>
        {tagline && <span className="mt-1.5 block whitespace-nowrap text-[9px] font-bold uppercase tracking-[.12em] text-muted">Document intelligence</span>}
      </span>
    </span>
  );
}
