import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { WebView } from "./web.jsx";
import { api } from "./api.js";

vi.mock("./api.js", async (orig) => ({ ...(await orig()), api: { web: vi.fn() } }));
afterEach(() => vi.clearAllMocks());

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
