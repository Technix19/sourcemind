"use client";

import { useEffect, useSyncExternalStore } from "react";
import { UiIcon } from "@/components/ui/UiIcon";

type Theme = "light" | "dark";
const STORAGE_KEY = "sourcemind.theme";
const CHANGE_EVENT = "sourcemind:theme-change";

let memoryPreference: Theme | null = null;

function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : memoryPreference;
  } catch {
    return memoryPreference;
  }
}

function snapshot(): Theme {
  if (typeof window === "undefined") return "light";
  const saved = storedTheme();
  if (saved) return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function serverSnapshot(): Theme {
  return "light";
}

function subscribe(notify: () => void): () => void {
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  window.addEventListener(CHANGE_EVENT, notify);
  window.addEventListener("storage", notify);
  media?.addEventListener?.("change", notify);
  return () => {
    window.removeEventListener(CHANGE_EVENT, notify);
    window.removeEventListener("storage", notify);
    media?.removeEventListener?.("change", notify);
  };
}

/** Persist the explicit selection, while first-time visitors follow their OS setting. */
function setTheme(next: Theme) {
  memoryPreference = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // A blocked storage API must not prevent the user from switching themes.
  }
  document.documentElement.dataset.theme = next;
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const theme = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const isDark = theme === "dark";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={
        "inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-line bg-white text-muted transition-colors hover:bg-ink hover:text-text dark:bg-[#202134] dark:hover:bg-[#302a46] " +
        className
      }
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      <UiIcon name={isDark ? "sun" : "moon"} size={18} />
    </button>
  );
}
