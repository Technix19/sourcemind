import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerText } from "./AnswerText";
import type { Evidence } from "@/lib/types";

const ev = (n: number): Evidence => ({
  citation_id: String(n), chunk_id: `c${n}`, document_id: "d", filename: "paper.pdf",
  page_number: n + 1, excerpt: "text", score: 0.5,
});

describe("AnswerText", () => {
  it("turns resolvable markers into buttons that report the citation", async () => {
    const onCite = vi.fn();
    render(<AnswerText text="Alpha [1] and beta [2]." evidence={[ev(1), ev(2)]} onCite={onCite} />);
    await userEvent.click(screen.getByRole("button", { name: "Show source 2: paper.pdf, page 3" }));
    expect(onCite).toHaveBeenCalledWith("2");
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("leaves a marker with no matching evidence as inert text", () => {
    render(<AnswerText text="Real [1] and phantom [7]." evidence={[ev(1)]} onCite={vi.fn()} />);
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText(/\[7\]/)).toBeInTheDocument();
  });

  it("renders markup in an answer as text, never as HTML", () => {
    const { container } = render(
      <AnswerText text={'<img src=x onerror="alert(1)"><script>alert(2)</script> ok [1]'} evidence={[ev(1)]} onCite={vi.fn()} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(2)</script>");
  });

  it("keeps paragraph breaks", () => {
    const { container } = render(<AnswerText text={"One [1].\n\nTwo."} evidence={[ev(1)]} onCite={vi.fn()} />);
    expect(container.querySelectorAll("p")).toHaveLength(2);
  });
});
