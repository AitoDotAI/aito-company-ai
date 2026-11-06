import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { WebView } from "./web.jsx";
import { api } from "./api.js";

vi.mock("./api.js", async (orig) => ({ ...(await orig()), api: { web: vi.fn(), webKpi: vi.fn(), webPaths: vi.fn() } }));
import { setPublicDemo } from "./session.js";
afterEach(() => { vi.clearAllMocks(); setPublicDemo(false); });

const BUNDLE = {
  since: "2026-10-06", until: "2026-11-04", filters: {},
  totals: { sessions: 120, onward_clicks: 18, signup_ctas: 3, bots: 4 },
  days: [{ day: "2026-11-03", sessions: 70, onward_clicks: 10, signup_ctas: 2 },
         { day: "2026-11-04", sessions: 50, onward_clicks: 8, signup_ctas: 1 }],
  facets: { source: ["direct", "organic", "referral"], device_class: ["desktop", "mobile"],
            utm_campaign: ["ecom-screen"], landing_path: ["/", "/pricing/"] },
  drivers: { population: 120, with_outcome: 18, relations: [
    { field: "source", value: "referral", lift: 2.4, rate_with: 0.36, rate_without: 0.12, rows_with: 11, thin: false },
    { field: "country", value: "Finland", lift: 3.1, rate_with: 0.5, rate_without: 0.14, rows_with: 4, thin: true },
  ], request: { from: "web_sessions" } },
  next_paths: null,
  thin_below: 5,
  kpis: { pricing_page: 9, contact_page: 2, login_page: 14, signup: 3, sandbox: 2,
          data_loaded: 0, first_query: 1, api_keys: 0 },
  session_total: 124,
  sessions: [{ day: "2026-11-04", hour: 9, landing_path: "/pricing/", next_path: "/contact-us/",
               source: "organic", referrer_domain: "google.com", utm_campaign: null, post_id: null,
               device_class: "desktop", country: "Finland", views: 2, engaged_seconds: 40,
               onward_click: true, signup_cta: false, likely_bot: false }],
};

describe("web view", () => {
  it("shows the KPIs, Aito's drivers with their counts, and the sessions", async () => {
    api.web.mockResolvedValue(BUNDLE);
    render(<WebView />);
    const kpis = within(await screen.findByTestId("web-kpis"));
    expect(kpis.getByText("120")).toBeInTheDocument();
    expect(kpis.getByText("15%")).toBeInTheDocument();                // 18 / 120 onward
    const drivers = within(screen.getByTestId("web-drivers"));
    expect(drivers.getByText("source = referral")).toBeInTheDocument();
    expect(drivers.getByText(/2\.4×/)).toBeInTheDocument();
    expect(drivers.getByText(/11 sessions/)).toBeInTheDocument();
    expect(drivers.getByText(/thin/)).toBeInTheDocument();              // 4 sessions: no bare claim
    expect(screen.getByText(/fewer than 5 sessions/)).toBeInTheDocument();
    const table = within(screen.getByTestId("web-sessions"));
    expect(table.getByText("/pricing/")).toBeInTheDocument();
    expect(table.getByText("google.com")).toBeInTheDocument();
    expect(screen.getByText(/1–1 of 124/)).toBeInTheDocument();
  });

  it("filters through the API and asks for next pages on a landing page", async () => {
    api.web.mockResolvedValue(BUNDLE);
    render(<WebView />);
    await screen.findByTestId("web-kpis");
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "organic" } });
    await waitFor(() => expect(api.web).toHaveBeenLastCalledWith(expect.objectContaining({ source: "organic" })));
    api.web.mockResolvedValue({ ...BUNDLE, next_paths: { request: {}, hits: [{ value: "/contact-us/", p: 0.42 }] } });
    fireEvent.change(screen.getByLabelText("Landing page"), { target: { value: "/pricing/" } });
    await waitFor(() => expect(api.web).toHaveBeenLastCalledWith(expect.objectContaining({ path: "/pricing/" })));
    const next = within(await screen.findByTestId("web-next"));
    expect(next.getByText("/contact-us/")).toBeInTheDocument();
    expect(next.getByText("42%")).toBeInTheDocument();
  });
});


const KPI_ANSWER = {
  target: { kpi: "sandbox" }, sessions: 120, with_target: 2, thin_below: 5,
  dropped_as_linked: ["kpi_login_page", "kpi_signup"], dropped_own_events: ["instance_create"],
  drivers: { relations: [{ field: "source", value: "direct", lift: 1.8, rate_with: 0.03, rate_without: 0.01, rows_with: 2, thin: true }] },
  other_kpis: { relations: [{ field: "kpi_pricing_page", value: true, lift: 4.0, rate_with: 0.2, rate_without: 0.05, rows_with: 9, thin: false }] },
  other_events: { relations: [] },
  acquisition: { relations: [{ field: "first_landing_path", value: "/blog/", lift: 2.0, rate_with: 0.1, rate_without: 0.05, rows_with: 3, thin: true }] },
  journeys: [{ label: "visitor 1", sessions: [{ day: "2026-11-04", hour: 9, landing_path: "/blog/", source: "direct", events: "page:/blog/" }] }],
};

describe("web view KPIs", () => {
  it("lists the KPIs and opens one with its insights", async () => {
    api.web.mockResolvedValue(BUNDLE);
    api.webKpi.mockResolvedValue(KPI_ANSWER);
    render(<WebView />);
    const kpis = within(await screen.findByTestId("web-kpis"));
    fireEvent.click(kpis.getByRole("button", { name: /Sandbox/ }));
    await waitFor(() => expect(api.webKpi).toHaveBeenLastCalledWith(expect.objectContaining({ kpi: "sandbox" })));
    expect(await screen.findByText(/login_page, signup/)).toBeInTheDocument();          // dropped as linked
    expect(screen.getByText("source = direct")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Other KPIs" }));
    expect(screen.getByText("kpi_pricing_page = true")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Acquisition" }));
    expect(screen.getByText("first_landing_path = /blog/")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Journeys" }));
    expect(screen.getByText("visitor 1")).toBeInTheDocument();
  });

  it("never offers journeys on a public demo", async () => {
    setPublicDemo(true);
    api.web.mockResolvedValue(BUNDLE);
    api.webKpi.mockResolvedValue({ ...KPI_ANSWER, journeys: [], journeys_hidden: true });
    render(<WebView />);
    const kpis = within(await screen.findByTestId("web-kpis"));
    fireEvent.click(kpis.getByRole("button", { name: /Sandbox/ }));
    await screen.findByRole("tab", { name: "Drivers" });
    expect(screen.queryByRole("tab", { name: "Journeys" })).toBeNull();
  });
});


describe("web view paths", () => {
  it("shows the top paths, the pages that raise it, and the drop-off for a KPI", async () => {
    api.web.mockResolvedValue(BUNDLE);
    api.webKpi.mockResolvedValue(KPI_ANSWER);
    api.webPaths.mockResolvedValue({
      kpi: "sandbox", thin_below: 5, kpi_steps: 9,
      top_paths: [{ path: ["page:/", "page:/blog/", "kpi:sandbox"], visits: 5, lift: 3.5, thin: false }],
      raises_later: { relations: [{ field: "token", value: "page:/pricing/", lift: 2.1, rate_with: 0.4, rate_without: 0.2, rows_with: 12, thin: false }] },
      drop_off: { relations: [{ field: "token", value: "page:/blog/", lift: 1.4, rate_with: 0.9, rate_without: 0.6, rows_with: 3, thin: true }] },
    });
    render(<WebView />);
    const kpis = within(await screen.findByTestId("web-kpis"));
    fireEvent.click(kpis.getByRole("button", { name: /Sandbox/ }));
    fireEvent.click(await screen.findByRole("tab", { name: "Paths" }));
    await waitFor(() => expect(api.webPaths).toHaveBeenLastCalledWith(expect.objectContaining({ kpi: "sandbox" })));
    expect(await screen.findByText("page:/ → page:/blog/ → kpi:sandbox")).toBeInTheDocument();
    expect(screen.getByText("token = page:/pricing/")).toBeInTheDocument();
    expect(screen.getByText("token = page:/blog/")).toBeInTheDocument();
  });
});
