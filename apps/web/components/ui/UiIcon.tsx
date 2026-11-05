import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "message" | "file" | "chart" | "chevron" | "search" | "upload"
  | "arrow" | "plus" | "folder" | "logout" | "layers" | "check"
  | "info" | "external" | "trash" | "menu" | "x" | "send" | "refresh";

const paths: Record<IconName, ReactNode> = {
  message: <><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5 8 8 0 0 1-3.4-.7L4 20l1.6-4.7A7.5 7.5 0 1 1 20 11.5Z" /></>,
  file: <><path d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></>,
  chart: <><path d="M4 20V12h4v8M10 20V4h4v16M16 20v-9h4v9M3 20h18"/></>,
  chevron: <path d="m6 9 6 6 6-6"/>,
  search: <><circle cx="10.8" cy="10.8" r="6.7"/><path d="m16 16 4.5 4.5"/></>,
  upload: <><path d="M12 15V3m-4 4 4-4 4 4"/><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"/></>,
  arrow: <><path d="M4 12h16m-6-6 6 6-6 6"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  folder: <path d="M3 6h7l2 2h9v11H3V6Z"/>,
  logout: <><path d="M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 7l5 5-5 5M9 12h11"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5ZM3 13l9 5 9-5M3 18l9 5 9-5"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/></>,
  external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M20 13v7H4V4h7"/></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  x: <path d="M5 5l14 14M19 5 5 19"/>,
  send: <><path d="m3 11 18-8-8 18-2.5-7.5L3 11Z"/><path d="m10.5 13.5 5-5"/></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 6M4 12l2 6A7 7 0 0 0 18.5 15"/></>,
};

export function UiIcon({ name, size = 18, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" {...props}
    >
      {paths[name]}
    </svg>
  );
}
