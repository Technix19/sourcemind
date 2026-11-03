import { describe, expect, it } from "vitest";
import { splitCitations } from "./citations";

describe("splitCitations", () => {
  it("returns plain text untouched", () => {
    expect(splitCitations("No markers here.")).toEqual([{ type: "text", text: "No markers here." }]);
    expect(splitCitations("")).toEqual([]);
  });

  it("splits text around a single marker", () => {
    expect(splitCitations("A fact [1]. More.")).toEqual([
      { type: "text", text: "A fact " },
      { type: "cite", raw: "[1]", numbers: ["1"] },
      { type: "text", text: ". More." },
    ]);
  });

  it("handles grouped and adjacent markers", () => {
    const segments = splitCitations("Both [1, 2][3]");
    expect(segments.filter((s) => s.type === "cite")).toEqual([
      { type: "cite", raw: "[1, 2]", numbers: ["1", "2"] },
      { type: "cite", raw: "[3]", numbers: ["3"] },
    ]);
  });

  it("ignores things that only look like markers", () => {
    expect(splitCitations("array[i] and [abc] and [ 1 ]").every((s) => s.type === "text")).toBe(true);
  });
});
