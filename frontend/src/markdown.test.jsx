import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Markdown } from "./markdown.jsx";

// Render to a container and hand back its node for assertions.
function md(text) {
  const { container } = render(<Markdown text={text} />);
  return container.querySelector(".md");
}

describe("Markdown renderer", () => {
  // The regression that froze the Library: the heading branch never advanced
  // the line cursor, so any '# ...' line spun the parse loop forever. Every
  // doc starts with a title, so this guards the exact freeze. A hang would
  // blow vitest's per-test timeout and fail loudly rather than wedging.
  it("terminates and renders a document that starts with a heading", () => {
    const root = md("# Title\n\nA paragraph.\n");
    expect(root.querySelector("h2")).toHaveTextContent("Title");
    expect(root.querySelector("p")).toHaveTextContent("A paragraph.");
  });

  it("terminates on consecutive headings (no line left unconsumed)", () => {
    const root = md("# One\n## Two\n### Three\n");
    const headings = [...root.querySelectorAll("h2,h3,h4")].map((h) => h.textContent);
    expect(headings).toEqual(["One", "Two", "Three"]);
  });

  it("maps heading levels: '#'→h2 … capped at h5", () => {
    const root = md("# a\n## b\n#### d\n");
    expect(root.querySelector("h2")).toHaveTextContent("a");
    expect(root.querySelector("h3")).toHaveTextContent("b");
    expect(root.querySelector("h5")).toHaveTextContent("d");
  });

  it("renders fenced code blocks verbatim", () => {
    const root = md("```\nconst x = 1;\nfoo();\n```\n");
    const code = root.querySelector("pre code");
    expect(code).toHaveTextContent("const x = 1;");
    expect(code.textContent).toContain("foo();");
  });

  it("renders unordered lists", () => {
    const root = md("- one\n- two\n- three\n");
    const items = [...root.querySelectorAll("ul li")].map((li) => li.textContent);
    expect(items).toEqual(["one", "two", "three"]);
  });

  it("renders tables with a header and body rows", () => {
    const root = md("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n");
    expect([...root.querySelectorAll("thead th")].map((c) => c.textContent)).toEqual(["a", "b"]);
    const body = [...root.querySelectorAll("tbody tr")].map((r) =>
      [...r.querySelectorAll("td")].map((c) => c.textContent));
    expect(body).toEqual([["1", "2"], ["3", "4"]]);
  });

  it("renders inline code, bold, and links", () => {
    const root = md("Use `code`, be **bold**, see [docs](https://x.dev).\n");
    expect(root.querySelector("code")).toHaveTextContent("code");
    expect(root.querySelector("strong")).toHaveTextContent("bold");
    const a = root.querySelector("a");
    expect(a).toHaveTextContent("docs");
    expect(a).toHaveAttribute("href", "https://x.dev");
  });

  it("handles empty and whitespace-only input without error", () => {
    expect(md("").childElementCount).toBe(0);
    expect(md("\n\n\n").childElementCount).toBe(0);
  });

  it("does not hang on an unterminated code fence", () => {
    // missing closing ``` — must still terminate (loop bound by lines.length)
    const root = md("```\nunclosed\nstill going\n");
    expect(root.querySelector("pre code")).toHaveTextContent("unclosed");
  });
});
