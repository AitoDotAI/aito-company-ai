import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TechTree } from "./techtree.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({ api: { techTree: vi.fn(),
  document: vi.fn(() => Promise.resolve({ doc_id: "dc1", title: "Engine notes", body: "Short." })) } }));
afterEach(() => vi.clearAllMocks());

const node = (o) => ({ metric: "m", what: "w", state: "s", next: "n", owner: "o",
  requires: [], doc_id: null, updated_on: "2026-11-15", ...o });
const TREE = {
  eras: ["Foundations", "Proven", "Hardening", "Customer-ready", "In market"],
  statuses: { done: "Researched", active: "In progress", open: "Ready to start",
              decision: "Your decision", locked: "Locked" },
  branches: ["Core", "Apps"],
  request: { from: "tech_nodes" },
  nodes: [
    node({ node_id: "a", title: "Base engine", branch: "Core", era: 0, row: 0, status: "done", doc_id: "dc1",
           recommendation: "Keep quoting it.", reasons: "It holds up under scrutiny." }),
    node({ node_id: "b", title: "Faster engine", branch: "Core", era: 1, row: 0, status: "active", requires: ["a"] }),
    node({ node_id: "c", title: "App on top", branch: "Apps", era: 2, row: 1, status: "locked", requires: ["b"] }),
  ],
};

describe("Tech tree view", () => {
  it("draws an edge for each prerequisite", async () => {
    api.techTree.mockResolvedValue(TREE);
    const { container } = render(<TechTree />);
    await screen.findByText("Faster engine");
    const edges = [...container.querySelectorAll("svg.tt-edges path")]
      .map((p) => `${p.dataset.from}->${p.dataset.to}`).sort();
    expect(edges).toEqual(["a->b", "b->c"]);
  });

  it("hovering a node lights its whole prerequisite chain", async () => {
    api.techTree.mockResolvedValue(TREE);
    const { container } = render(<TechTree />);
    fireEvent.mouseEnter(await screen.findByRole("button", { name: /App on top/ }));
    const hot = [...container.querySelectorAll("svg.tt-edges path.hot")]
      .map((p) => `${p.dataset.from}->${p.dataset.to}`).sort();
    expect(hot).toEqual(["a->b", "b->c"]);
    expect(screen.getByRole("button", { name: /Base engine/ })).toHaveClass("chain");
  });

  it("opens a panel with requires, unlocks and the document link", async () => {
    api.techTree.mockResolvedValue(TREE);
    render(<TechTree />);
    fireEvent.click(await screen.findByRole("button", { name: /Base engine/ }));
    const panel = screen.getByTestId("tt-panel");
    expect(panel).toHaveTextContent("Researched");
    expect(panel).toHaveTextContent("Faster engine");          // unlocks
    expect(screen.getByRole("link", { name: /open the article/i })).toHaveAttribute("href", "#/documents/dc1");
    fireEvent.click(await screen.findByRole("button", { name: /App on top/ }));
    expect(screen.getByTestId("tt-panel")).not.toHaveTextContent("open the article");
  });

  it("the legend dims a status it filters out", async () => {
    api.techTree.mockResolvedValue(TREE);
    render(<TechTree />);
    await screen.findByText("Faster engine");
    fireEvent.click(screen.getByRole("button", { name: /^In progress/ }));
    expect(screen.getByRole("button", { name: /Faster engine/ })).toHaveClass("dim");
    expect(screen.getByRole("button", { name: /Base engine/ })).not.toHaveClass("dim");
  });

  it("shows the recommendation box under the title when a node has one", async () => {
    api.techTree.mockResolvedValue(TREE);
    api.document.mockResolvedValue({ doc_id: "dc1", title: "Engine notes", body: "# Engine notes\n\nThe base engine is measured.\nTwice.\n\n## More\n\nDetail." });
    render(<TechTree />);
    fireEvent.click(await screen.findByRole("button", { name: /Base engine/ }));
    const box = screen.getByTestId("tt-rec");
    expect(box).toHaveTextContent("Keep quoting it.");
    expect(box).toHaveTextContent("Why: It holds up under scrutiny.");
    // right under the title, before the details
    const panel = screen.getByTestId("tt-panel");
    expect(panel.querySelector("h2").nextElementSibling.nextElementSibling).toBe(box);
  });

  it("hides the box when a node has neither a recommendation nor reasons", async () => {
    api.techTree.mockResolvedValue(TREE);
    render(<TechTree />);
    fireEvent.click(await screen.findByRole("button", { name: /Faster engine/ }));
    expect(screen.queryByTestId("tt-rec")).not.toBeInTheDocument();
  });

  it("shows the article's first paragraph as context when doc_id is set", async () => {
    api.techTree.mockResolvedValue(TREE);
    api.document.mockResolvedValue({ doc_id: "dc1", title: "Engine notes", body: "# Engine notes\n\nThe base engine is measured.\nTwice.\n\n## More\n\nDetail." });
    render(<TechTree />);
    fireEvent.click(await screen.findByRole("button", { name: /Base engine/ }));
    expect(api.document).toHaveBeenCalledWith("dc1");
    const ctx = await screen.findByTestId("tt-context");
    expect(ctx).toHaveTextContent("The base engine is measured. Twice.");
    expect(ctx).not.toHaveTextContent("Detail.");
    fireEvent.click(screen.getByRole("button", { name: /Faster engine, In progress/ }));
    expect(screen.queryByTestId("tt-context")).not.toBeInTheDocument();
    expect(api.document).toHaveBeenCalledTimes(1);
  });

  it("shows the error instead of an empty map", async () => {
    api.techTree.mockRejectedValue(new Error("tech_nodes not found"));
    render(<TechTree />);
    expect(await screen.findByText(/tech_nodes not found/)).toBeInTheDocument();
  });
});
