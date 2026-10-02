import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraphView } from "./views.jsx";
import { api } from "./api.js";

// Each card shows the request as it was sent: the endpoint and the body,
// nested `from` included. The base rate the headline quotes is a card too.
vi.mock("./api.js", () => ({ api: { graph: vi.fn() } }));

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
