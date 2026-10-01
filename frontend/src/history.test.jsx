import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { VIEWS, Scorer } from "./views.jsx";
import { api } from "./api.js";

// No finished history (no deal closed, no post measured) is a state, not a number:
// the backend returns p_win null (deals: basis "no_history") and the UI says why.
vi.mock("./api.js", () => ({
  api: { deals: vi.fn(), whoToReach: vi.fn(), salesTrend: vi.fn(), funnel: vi.fn(),
         funnelCatalog: vi.fn(), score: vi.fn(), scoreOptions: vi.fn(),
         pwin: vi.fn(() => Promise.resolve({ p_win: null, why: [], n: 0, basis: "no_history" })),
         users: vi.fn(() => Promise.resolve({ users: [] })),
         assignments: vi.fn(() => Promise.resolve({ map: {} })), assign: vi.fn() },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

afterEach(() => vi.clearAllMocks());

describe("no finished history", () => {
  it("a pipeline deal with no closed history says so instead of a P(won)", async () => {
    api.deals.mockResolvedValue({
      kpis: { weighted_pipeline: 2000, open_value: 5000, open_deals: 1, stalled: 0 },
      deals: [{ deal_id: "d1", company: "Oscorp OÜ", stage: "pilot", value_eur: 5000,
                probability: 40, weighted_value: 2000, p_win: null, n: 0, basis: "no_history",
                blocker: "none", why: [] }],
    });
    render(VIEWS.sales.tabs.find((t) => t.id === "pipeline").render());
    expect(await screen.findByText(/no closed deals yet/)).toBeInTheDocument();
  });

  it("who to reach labels a no-history row", async () => {
    api.deals.mockResolvedValue({ kpis: { weighted_pipeline: 0, open_value: 0, open_deals: 0, stalled: 0 },
                                  deals: [] });
    api.whoToReach.mockResolvedValue({
      as_of: "2026-10-01", count: 1,
      rows: [{ company: "Hooli Oy", deal_id: "d10", stage: "lead", p_win: null, n: 0, basis: "no_history",
               days_since_touch: 30, contacts: [] }],
    });
    api.salesTrend.mockResolvedValue({ win_rate: null, avg_cycle_days: null, won: 0, closed: 0, quarters: [] });
    api.funnelCatalog.mockResolvedValue({
      funnels: [{ key: "sales", label: "Sales funnel", dimensions: [], values: {} }] });
    api.funnel.mockResolvedValue({ deepest_label: "meeting", outlook: { p: null }, causes: [], leak: null,
                                   stages: [], lever: null });
    render(VIEWS.salesanalytics.render());
    expect(await screen.findByText(/P\(won\) · no closed deals yet/)).toBeInTheDocument();
  });

  it("the post scorer with no measured post shows no gauge number", async () => {
    api.scoreOptions.mockResolvedValue({ platforms: ["linkedin"], features: [],
                                         options: { platform: ["linkedin"] } });
    api.score.mockResolvedValue({ platform: "linkedin", features: {}, p_win: null, base_p_win: null,
                                  why: [], levers: [] });
    render(<Scorer />);
    expect(await screen.findByText(/Not enough history: no post has been measured yet/)).toBeInTheDocument();
    expect(screen.queryByText(/predicted P\(win\) for this draft/)).not.toBeInTheDocument();
  });
});
