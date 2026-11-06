import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { GraphView } from "./views.jsx";
import { layout } from "./graphlayout.js";
import { api } from "./api.js";

// Each card shows the request as it was sent: the endpoint and the body,
// nested `from` included. The base rate the headline quotes is a card too.
vi.mock("./api.js", () => ({ api: { graph: vi.fn(), graphNetwork: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

const CLOSED = { from: "deals", where: { stage: { $or: ["closed_lost", "closed_won"] } } };

describe("knowledge graph query panes", () => {
  it("show the endpoint and the real body, and the baseline query", async () => {
    api.graph.mockResolvedValue({
      baseline_p: 0.26, conditioned_p: 0.36, ok: 2, failed: [],
      answers: [
        { id: "cto-odds", question: "At an account where we know a CTO…", endpoint: "/api/v2/_query",
          request: { from: CLOSED, predict: "won" }, hits: [{ $value: true, $p: 0.36 }], total: 2 },
        { id: "baseline", question: "How likely is any closed deal to have been won?",
          endpoint: "/api/v2/_query", request: { from: CLOSED, predict: "won" },
          hits: [{ $value: true, $p: 0.26 }], total: 2 },
      ],
    });
    render(<GraphView />);
    expect(await screen.findByText("How likely is any closed deal to have been won?")).toBeInTheDocument();
    expect(screen.getAllByText("POST /api/v2/_query")).toHaveLength(2);
    expect(screen.getAllByText(/"closed_won"/).length).toBeGreaterThan(0);   // the nested from is shown
    expect(screen.getByText(/26% base rate across closed deals/)).toBeInTheDocument();
  });

  it("a card with no closed history says so", async () => {
    api.graph.mockResolvedValue({
      baseline_p: null, conditioned_p: null, ok: 1, failed: [],
      answers: [{ id: "baseline", question: "How likely is any closed deal to have been won?",
                  endpoint: "/api/v2/_query", request: { from: CLOSED, predict: "won" },
                  hits: [], total: 0, no_history: true }],
    });
    render(<GraphView />);
    expect(await screen.findByText(/no deal has closed yet/)).toBeInTheDocument();
  });
});


const NET = {
  nodes: [
    { id: "company:acme-o", kind: "company", label: "Acme Oy", company_id: "acme-o",
      facts: { industry: "accounting", relationship: "customer", country: "Estonia", mrr_eur: 17291,
               open_deals: 2, contact_count: 1, technical_contact: false } },
    { id: "company:wonka-oy", kind: "company", label: "Wonka Oy", company_id: "wonka-oy",
      facts: { industry: "analytics", relationship: "prospect", country: "Finland", mrr_eur: 0,
               open_deals: 1, contact_count: 1, technical_contact: true } },
    { id: "contact:sc001", kind: "contact", label: "Grace Marsh", role: "CFO", company_id: "acme-o" },
    { id: "deal:sd001", kind: "deal", label: "negotiation", stage: "negotiation", value_eur: 24500, company_id: "acme-o" },
  ],
  edges: [
    { source: "contact:sc001", target: "company:acme-o", kind: "works_at" },
    { source: "deal:sd001", target: "company:acme-o", kind: "deal_with" },
  ],
  counts: { company: 2, contact: 1, deal: 1 }, matched: [], query: null, filters: {},
  kinds: ["company", "contact", "deal"], unlinked_documents: 0, dropped_edges: 0, requests: [],
  facets: { industry: ["accounting", "analytics"], relationship: ["customer", "prospect"], country: ["Estonia", "Finland"] },
};

describe("knowledge graph explorer", () => {
  it("draws the companies and opens a node's facts and links", async () => {
    api.graph.mockResolvedValue({ answers: [], ok: 0, failed: [] });
    api.graphNetwork.mockResolvedValue(NET);
    render(<GraphView />);
    expect(await screen.findByText("Acme Oy")).toBeInTheDocument();
    expect(screen.getByText("Wonka Oy")).toBeInTheDocument();
    expect(screen.getByText(/2 companies · 1 people · 1 deals/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("node-company:acme-o"));
    const panel = within(screen.getByRole("complementary"));
    expect(await panel.findByText("customer")).toBeInTheDocument();
    expect(panel.getByText(/€17[\s,.]?291/)).toBeInTheDocument();
    expect(panel.getByRole("link", { name: /Open company/ })).toHaveAttribute("href", "#/company/acme-o");
    expect(panel.getByRole("button", { name: /Grace Marsh/ })).toBeInTheDocument();
  });

  it("searches and filters through the API", async () => {
    api.graph.mockResolvedValue({ answers: [], ok: 0, failed: [] });
    api.graphNetwork.mockResolvedValue(NET);
    render(<GraphView />);
    await screen.findByText("Acme Oy");
    fireEvent.change(screen.getByPlaceholderText(/Search the graph/), { target: { value: "acme" } });
    await waitFor(() => expect(api.graphNetwork).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "acme" })));
    fireEvent.change(screen.getByLabelText("Relationship"), { target: { value: "customer" } });
    await waitFor(() => expect(api.graphNetwork).toHaveBeenLastCalledWith(
      expect.objectContaining({ relationship: "customer" })));
    fireEvent.click(screen.getByLabelText("Notes"));
    await waitFor(() => expect(api.graphNetwork).toHaveBeenLastCalledWith(
      expect.objectContaining({ kinds: "company,contact,deal,document" })));
  });

  it("unfolds one account: its rows, each fact's source, and back", async () => {
    api.graph.mockResolvedValue({ answers: [], ok: 0, failed: [] });
    const UNFOLD = {
      nodes: [
        { ...NET.nodes[0], hold: null,
          basis: { industry: { value: "accounting", rows: ["sc001"], why: "1 of 1 contacts say accounting", matches: true },
                   country: { value: "Estonia", rows: ["sc001"], why: "1 of 1 contacts say Estonia", matches: true },
                   relationship: { value: "prospect", rows: ["sd009"], why: "1 deal open, none won", matches: false },
                   mrr_eur: { value: 17291, rows: ["sd001"], why: "won value 207500 / 12", matches: true } } },
        NET.nodes[2],
        { id: "document:sdc009", kind: "document", label: "Account plan", company_id: "acme-o" },
        { id: "fact:sfa001", kind: "fact", label: "Commercial lead owns the track", fact_kind: "role",
          slot: "decision_owner", valid_from: "2026-10-26", company_id: "acme-o",
          source: { kind: "doc", id: "sdc009", status: "linked", node: "document:sdc009" } },
        { id: "fact:sfa002", kind: "fact", label: "Sponsor decides", fact_kind: "role", slot: "decision_owner",
          valid_from: "2026-11-01", company_id: "acme-o",
          source: { kind: "doc", id: "doc-nope", status: "dangling", node: null } },
      ],
      edges: [
        { source: "contact:sc001", target: "company:acme-o", kind: "works_at" },
        { source: "fact:sfa001", target: "document:sdc009", kind: "said_in" },
        { source: "fact:sfa001", target: "company:acme-o", kind: "fact_of" },
        { source: "fact:sfa002", target: "company:acme-o", kind: "fact_of" },
      ],
      counts: { company: 1, contact: 1, document: 1, fact: 2 }, matched: ["company:acme-o"], query: null,
      filters: {}, focus: "acme-o", kinds: [], unlinked_documents: 0, dropped_edges: 0, requests: [], facets: {},
    };
    api.graphNetwork.mockImplementation((p) => Promise.resolve(p.focus ? UNFOLD : NET));
    render(<GraphView />);
    await screen.findByText("Acme Oy");
    fireEvent.click(screen.getByTestId("node-company:acme-o"));
    fireEvent.click(within(screen.getByRole("complementary")).getByRole("button", { name: /Unfold/ }));
    await waitFor(() => expect(api.graphNetwork).toHaveBeenLastCalledWith({ focus: "acme-o" }));
    expect(await screen.findByText(/Unfolded: Acme Oy/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("node-company:acme-o"));
    const panel = within(screen.getByRole("complementary"));
    expect(panel.getByText("1 of 1 contacts say accounting")).toBeInTheDocument();
    expect(panel.getByText(/its rows now say prospect/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("node-fact:sfa001"));
    expect(within(screen.getByRole("complementary")).getByText(/said in doc sdc009/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("node-fact:sfa002"));
    expect(within(screen.getByRole("complementary")).getByText(/doc doc-nope: not found/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Whole graph/ }));
    await waitFor(() => expect(api.graphNetwork).toHaveBeenLastCalledWith(
      expect.objectContaining({ kinds: "company,contact,deal" })));
  });

  it("lays the same graph out the same way, inside the box", () => {
    const a = layout(NET.nodes, NET.edges, { width: 400, height: 300 });
    const b = layout(NET.nodes, NET.edges, { width: 400, height: 300 });
    expect([...a.entries()]).toEqual([...b.entries()]);
    for (const { x, y } of a.values()) {
      expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThanOrEqual(400);
      expect(y).toBeGreaterThanOrEqual(0); expect(y).toBeLessThanOrEqual(300);
    }
  });
});
