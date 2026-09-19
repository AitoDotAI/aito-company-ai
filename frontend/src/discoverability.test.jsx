import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Documents, CompanyDetail, SearchView, QuickFind } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    documents: vi.fn(), createDocument: vi.fn(), updateDocument: vi.fn(),
    deleteDocument: vi.fn(), todoOptions: vi.fn(),
    companyDetail: vi.fn(), search: vi.fn(), searchClick: vi.fn(), quickFind: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

beforeEach(() => { window.location.hash = ""; });
afterEach(() => vi.clearAllMocks());

const DOCS = { count: 3, documents: [
  { doc_id: "dc1", title: "Ideal customer profile", body: "Nordic SaaS", kind: "internal",
    area: "sales", company_eff: null, contact_name: null, topics: null, updated: "2026-06-02" },
  { doc_id: "dc2", title: "Genco account plan", body: "pilot", kind: "internal",
    area: "sales", company_eff: "Genco Oy", contact_name: "Carol", topics: "pilot", updated: "2026-06-10" },
  { doc_id: "dc3", title: "Acme note", body: "robin", kind: "internal",
    area: null, company_eff: "Acme", contact_name: null, topics: "customer", updated: "2026-06-15" },
]};

describe("Documents view — search + deep-link open", () => {
  it("filters notes by the search box", async () => {
    api.documents.mockResolvedValue(DOCS);
    api.todoOptions.mockResolvedValue({ contacts: [] });
    render(<Documents />);
    await screen.findByText("Ideal customer profile");
    fireEvent.change(screen.getByPlaceholderText(/filter notes/i), { target: { value: "acme" } });
    await waitFor(() => expect(screen.queryByText("Ideal customer profile")).not.toBeInTheDocument());
    expect(screen.getByText("Acme note")).toBeInTheDocument();
  });

  it("opens a specific note via openDoc (deep link)", async () => {
    api.documents.mockResolvedValue(DOCS);
    api.todoOptions.mockResolvedValue({ contacts: [] });
    render(<Documents openDoc="dc3" />);
    // the selected doc's body renders in the reader pane
    await screen.findByText(/robin/i);
  });
});

describe("Search results are openable", () => {
  it("clicking a doc hit navigates to the note", async () => {
    api.searchClick.mockResolvedValue({});
    api.search.mockResolvedValue({
      query: "genco", count: 1, context_id: "ctx1", learned: false,
      hits: [{ item_id: "doc:dc2", kind: "doc", source_id: "dc2", title: "Genco account plan", tags: "pilot" }],
    });
    render(<SearchView />);
    fireEvent.change(screen.getByPlaceholderText(/Search docs/i), { target: { value: "genco" } });
    fireEvent.click(screen.getByText("Search"));
    const hit = await screen.findByText("Genco account plan");
    fireEvent.click(hit);
    expect(api.searchClick).toHaveBeenCalledWith("ctx1", "doc:dc2");
    expect(window.location.hash).toBe("#/documents/dc2");
  });
});

describe("Company drill-in", () => {
  it("shows the company's notes and opens one on click", async () => {
    api.companyDetail.mockResolvedValue({
      company_id: "genco-oy", name: "Genco Oy",
      contacts: [{ id: "sc1", name: "Carol Lane", role: "Partner" }],
      deals: [], documents: [{ doc_id: "dc2", title: "Genco account plan", noted_on: null, topics: "pilot", kind: "internal" }],
    });
    render(<CompanyDetail companyId="genco-oy" />);
    await screen.findByText("Genco Oy");
    expect(screen.getByText("Carol Lane")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Genco account plan"));
    expect(window.location.hash).toBe("#/documents/dc2");
  });
});

describe("Global quick-find (top row)", () => {
  it("finds across entities and opens on click", async () => {
    api.quickFind.mockResolvedValue({ query: "genco", groups: [
      { kind: "company", items: [{ label: "Genco Oy", sub: null, target: "company/genco-oy" }] },
      { kind: "note", items: [{ label: "Genco account plan", sub: "2026-06-10", target: "documents/dc2" }] },
    ]});
    render(<QuickFind />);
    fireEvent.change(screen.getByPlaceholderText(/Find…/i), { target: { value: "genco" } });
    await screen.findByText("Genco Oy");
    expect(screen.getByText("Genco account plan")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByText("Genco account plan"));
    expect(window.location.hash).toBe("#/documents/dc2");
  });
});
