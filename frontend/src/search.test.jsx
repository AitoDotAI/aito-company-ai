import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { VIEWS } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: { search: vi.fn(), searchClick: vi.fn() },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

afterEach(() => vi.clearAllMocks());

const renderSearch = () => render(VIEWS.search.render());

const RESULTS = {
  query: "pricing", kind: null, count: 2, learned: false, context_id: "ctx_abc",
  hits: [
    { item_id: "doc:pricing.md", kind: "doc", source_id: "pricing.md", title: "Pricing playbook", tags: null },
    { item_id: "deal:sec1", kind: "deal", source_id: "sec1", title: "Soylent Oy — pilot", tags: "erp" },
  ],
};

describe("Search view", () => {
  it("prompts before a query, then shows ranked results on submit", async () => {
    api.search.mockResolvedValue(RESULTS);
    renderSearch();
    expect(screen.getByText(/type a query/)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Search docs/), { target: { value: "pricing" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText("Pricing playbook");
    expect(api.search).toHaveBeenCalledWith("pricing", "");
    // ranked, most relevant first
    expect(screen.getByText("Soylent Oy — pilot")).toBeInTheDocument();
    expect(screen.getByText(/2 results for/)).toBeInTheDocument();
  });

  it("clicking a result records the click (the training signal) once", async () => {
    api.search.mockResolvedValue(RESULTS);
    api.searchClick.mockResolvedValue({ clicked: true });
    renderSearch();
    fireEvent.change(screen.getByPlaceholderText(/Search docs/), { target: { value: "pricing" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    const row = await screen.findByText("Soylent Oy — pilot");
    fireEvent.click(row);
    await waitFor(() => expect(api.searchClick).toHaveBeenCalledWith("ctx_abc", "deal:sec1"));
    // clicking again does not double-record
    fireEvent.click(row);
    expect(api.searchClick).toHaveBeenCalledTimes(1);
  });

  it("passes the kind filter through", async () => {
    api.search.mockResolvedValue({ query: "accounting", kind: "deal", count: 0, hits: [] });
    renderSearch();
    fireEvent.change(screen.getByPlaceholderText(/Search docs/), { target: { value: "accounting" } });
    fireEvent.change(screen.getByTitle("kind"), { target: { value: "deal" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(api.search).toHaveBeenCalledWith("accounting", "deal"));
    await screen.findByText(/no matches for/);
  });
});
