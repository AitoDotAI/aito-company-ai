import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TabbedView } from "./App.jsx";
import { VIEWS } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: { companies: vi.fn(), deals: vi.fn(), todos: vi.fn(), funnel: vi.fn(), funnelCatalog: vi.fn(),
         whoToReach: vi.fn(), salesTrend: vi.fn(), todoOptions: vi.fn(),
         pwin: vi.fn(() => Promise.resolve({ p_win: 0.4, why: [] })),
         users: vi.fn(), assignments: vi.fn(), assign: vi.fn() },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

afterEach(() => vi.clearAllMocks());

describe("TabbedView", () => {
  it("renders a tab strip from view.tabs and switches panels", () => {
    const view = {
      tabs: [
        { id: "a", label: "Alpha", render: () => <div>panel-alpha</div> },
        { id: "b", label: "Beta", render: () => <div>panel-beta</div> },
      ],
    };
    render(<TabbedView view={view} />);
    expect(screen.getByText("panel-alpha")).toBeInTheDocument();
    expect(screen.queryByText("panel-beta")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    expect(screen.getByText("panel-beta")).toBeInTheDocument();
    expect(screen.queryByText("panel-alpha")).not.toBeInTheDocument();
  });

  it("appends a Data tab when the view declares data specs", () => {
    const view = {
      render: () => <div>overview-panel</div>,
      data: [{ table: "deals" }],
    };
    render(<TabbedView view={view} />);
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Data" })).toBeInTheDocument();
  });

  it("hides the strip for a single-tab view with no data", () => {
    const view = { render: () => <div>solo-panel</div> };
    const { container } = render(<TabbedView view={view} />);
    expect(screen.getByText("solo-panel")).toBeInTheDocument();
    expect(container.querySelector(".tabs")).toBeNull();
  });
});

describe("Sales view", () => {
  it("declares To do · Pipeline · Companies · Calls · Analytics tabs", () => {
    expect(VIEWS.sales.tabs.map((t) => t.label))
      .toEqual(["To do", "Pipeline", "Companies", "Calls", "Analytics"]);
  });

  it("Companies tab rolls up companies with contact count + pipeline", async () => {
    api.companies.mockResolvedValue({
      count: 2,
      companies: [
        { company: "Oscorp OÜ", contacts: 3, segment: "erp", stage: "meeting",
          deals: 3, open_deals: 2, pipeline_eur: 102500, won: false },
        { company: "Gringotts Ab", contacts: 1, segment: "ecommerce", stage: "—",
          deals: 4, open_deals: 0, pipeline_eur: 0, won: true },
      ],
    });
    const companiesTab = VIEWS.sales.tabs.find((t) => t.id === "companies");
    render(companiesTab.render());
    await screen.findByText("Oscorp OÜ");
    expect(screen.getByText(/3 contacts · erp · meeting/)).toBeInTheDocument();
    expect(screen.getByText(/€102.?500/)).toBeInTheDocument();   // separator is locale-dependent
    // a company with only closed deals shows "closed", not a pipeline figure
    expect(screen.getByText("4 closed")).toBeInTheDocument();
    expect(screen.getByText(/won/, { selector: ".co-won" })).toBeInTheDocument();
  });

  it("Pipeline tab shows an assignee picker per deal reflecting the current owner", async () => {
    api.deals.mockResolvedValue({
      kpis: { weighted_pipeline: 1000, open_value: 5000, open_deals: 1, stalled: 0 },
      deals: [{ deal_id: "d1", company: "Oscorp OÜ", stage: "meeting", value_eur: 5000,
                probability: 40, p_win: 0.4, blocker: "none", why: [] }],
    });
    api.users.mockResolvedValue({ users: [
      { user_id: "u_sdr", name: "Sam Rivera", role: "sdr", active: true }] });
    api.assignments.mockResolvedValue({ map: { "deals:d1": "u_sdr" } });
    api.assign.mockResolvedValue({});
    const pipelineTab = VIEWS.sales.tabs.find((t) => t.id === "pipeline");
    render(pipelineTab.render());
    await screen.findByText(/Oscorp OÜ/);
    const sel = await screen.findByTitle("assignee");
    expect(sel.value).toBe("u_sdr");            // current owner reflected
    fireEvent.change(sel, { target: { value: "" } });   // unassign
    await waitFor(() => expect(api.assign).toHaveBeenCalledWith("deals", "d1", null));
  });
});

describe("Sales analytics view", () => {
  it("shows KPIs, pipeline-by-stage, who-to-reach, and the sales funnel lever", async () => {
    api.deals.mockResolvedValue({
      kpis: { weighted_pipeline: 188000, open_value: 481000, open_deals: 15, stalled: 3 },
      deals: [
        { deal_id: "d1", company: "Acme", stage: "negotiation", value_eur: 200000, p_win: 0.66 },
        { deal_id: "d2", company: "Globex", stage: "demo", value_eur: 90000, p_win: 0.38 },
        { deal_id: "d3", company: "Initech", stage: "negotiation", value_eur: 12000, p_win: 0.60 },
      ],
    });
    api.whoToReach.mockResolvedValue({
      as_of: "2026-09-16", count: 1,
      rows: [{ company: "Oscorp OÜ", deal_id: "d9", stage: "pilot", p_win: 0.72, n: 25, basis: "profile",
               days_since_touch: 18, contacts: [{ contact_id: "c1", name: "Dana Fox", role: "CTO" }] },
             { company: "Hooli Oy", deal_id: "d10", stage: "lead", p_win: 0.25, n: 0, basis: "base_rate",
               days_since_touch: 30, contacts: [] },
             { company: "Wonka Ab", deal_id: "d11", stage: "demo", p_win: 0.31, n: 4, basis: "partial",
               thin: [{ feature: "segment", value: "robotics", n: 2 }], days_since_touch: 21, contacts: [] }],
    });
    api.salesTrend.mockResolvedValue({
      win_rate: 0.25, avg_cycle_days: 46, won: 16, closed: 65,
      quarters: [
        { label: "Q1·26", won: 6, closed: 16, win_rate: 0.375 },
        { label: "Q2·26", won: 4, closed: 12, win_rate: 0.333 },
      ],
    });
    api.funnelCatalog.mockResolvedValue({
      funnels: [{ key: "sales", label: "Sales funnel", dimensions: [], values: {} }] });
    api.funnel.mockResolvedValue({
      deepest_label: "meeting", outlook: { p: 0.18 }, causes: [], leak: null,
      stages: [
        { key: "all", label: "Contacts", count: 50, rate_of_top: 1 },
        { key: "meeting", label: "Meeting booked", count: 9, conversion_from_prev: 0.18, rate_of_top: 0.18 },
      ],
      lever: { field: "source", options: [{ value: "referral", p: 0.30 }] },
    });

    render(VIEWS.salesanalytics.render());
    // the weighted pipeline is the operator's own probabilities, not Aito's P(won): it says so
    expect(await screen.findByText("weighted pipeline (own %)")).toBeInTheDocument();
    expect(screen.getByText("Σ value × your probability, not Aito's")).toBeInTheDocument();
    expect(screen.queryByText("P(won) · value")).not.toBeInTheDocument();
    expect(screen.getByText("open value")).toBeInTheDocument();
    // the quarter trend chart arrives with the trend fetch (block renders only then)
    await waitFor(() => expect(screen.getByText(/Win rate by quarter/)).toBeInTheDocument());
    // the two negotiation deals aggregate into one row (count 2)
    expect(screen.getByText(/negotiation · 2/)).toBeInTheDocument();
    expect(screen.getByText(/demo · 1/)).toBeInTheDocument();
    // who to reach: the stalled, high-P(won) deal with its contact and P(won)
    await waitFor(() => expect(screen.getByText("Oscorp OÜ")).toBeInTheDocument());
    expect(screen.getByText(/Dana Fox/)).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    // the evidence behind each number is on the row, and a thin profile says it fell back
    expect(screen.getByText("P(won) · 25 like it")).toBeInTheDocument();
    expect(screen.getByText("P(won) · base rate (too few like it)")).toBeInTheDocument();
    expect(screen.getByText("P(won) · 4 like it · thin: segment")).toBeInTheDocument();
    // the sales funnel lever (the parity gap this view closes)
    await waitFor(() => expect(screen.getByText(/Lever: source/)).toBeInTheDocument());
  });

  it("is still routable on its own, for deep links", () => {
    expect(VIEWS.salesanalytics).toBeTruthy();
    expect(VIEWS.salesanalytics.title).toBe("Sales analytics");
  });
});

describe("an area view owns its own analytics", () => {
  // The rule this encodes: marketing analytics used to sit inline in the
  // Marketing page while sales analytics was a separate nav entry, so the two
  // work areas were shaped differently and the sales funnel appeared twice.
  // Each area now carries an Analytics tab, and the ANALYTICS nav group is for
  // cross-area views only.
  it("gives Sales and Marketing the same tab shape", () => {
    for (const key of ["sales", "marketing"]) {
      const labels = VIEWS[key].tabs.map((t) => t.label);
      expect(labels[0]).toBe("To do");
      expect(labels).toContain("Analytics");
    }
  });

  it("declares Marketing tabs, so the page is not one long scroll", () => {
    expect(VIEWS.marketing.tabs.map((t) => t.label))
      .toEqual(["To do", "Posts", "Analytics", "Scorer"]);
  });
});
