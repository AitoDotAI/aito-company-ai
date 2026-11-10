import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { FunnelView } from "./views.jsx";
import { api } from "./api.js";

// The web funnel (aito.ai's real visits) is reach per stage, not ordered steps:
// no step conversion, no "biggest drop", and one overlap row (CPO, 11.11.2026).
vi.mock("./api.js", async (orig) => ({ ...(await orig()), api: { funnel: vi.fn(), funnelCatalog: vi.fn() } }));
afterEach(() => vi.clearAllMocks());

const CATALOG = { funnels: [{ key: "web", label: "aito.ai visits (real traffic, bots out)",
                              dimensions: ["source"], values: { source: ["direct"] } }] };
const WEB = {
  funnel: "web", label: "aito.ai visits (real traffic, bots out)", slice: {}, ordered: false,
  stages: [
    { key: "sessions", label: "Sessions", count: 120, rate_of_top: 1, conversion_from_prev: null },
    { key: "onward", label: "Onward click", count: 18, rate_of_top: 0.15, conversion_from_prev: null },
    { key: "pricing", label: "Pricing page", count: 9, rate_of_top: 0.075, conversion_from_prev: null },
    { key: "signup", label: "Sign-up click", count: 3, rate_of_top: 0.025, conversion_from_prev: null },
  ],
  leak: null,
  overlap: { label: "of sign-up click sessions, also saw pricing", of: 3, also: 2, share: 2 / 3 },
  outlook: { p: 0.02, why: [] }, deepest_label: "Sign-up click", causes: [], lever: null,
};

describe("the web funnel", () => {
  it("shows each stage's reach with no step conversion, and the overlap", async () => {
    api.funnelCatalog.mockResolvedValue(CATALOG);
    api.funnel.mockResolvedValue(WEB);
    render(<FunnelView only="web" />);
    expect(await screen.findByText("Sign-up click")).toBeInTheDocument();
    expect(screen.queryByText(/continue/)).toBeNull();
    expect(screen.queryByText(/biggest drop/)).toBeNull();
    expect(screen.queryByText(/Why it leaks/)).toBeNull();
    expect(screen.getByText(/What goes with a sign-up click/)).toBeInTheDocument();
    expect(screen.getByText(/2 of 3 · of sign-up click sessions, also saw pricing/)).toBeInTheDocument();
  });
});
