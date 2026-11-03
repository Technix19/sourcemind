import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { installViewportStubs, setWideScreen } from "./vitest.viewport";

beforeEach(() => {
  setWideScreen(true); // default: desktop layout
  installViewportStubs();
});

afterEach(() => {
  cleanup();
});

// jsdom does not implement these; the UI calls them when focusing evidence.
Element.prototype.scrollIntoView = vi.fn();
