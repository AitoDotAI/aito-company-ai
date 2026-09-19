import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Advisory } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    advisors: vi.fn(), advisory: vi.fn(), runAdvisory: vi.fn(), reflectAdvisor: vi.fn(),
    createAdvisor: vi.fn(), updateAdvisor: vi.fn(), removeAdvisor: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const ROSTER = {
  reads: ["deal_pipeline", "funnel", "experiment_board"],
  advisors: [
    { key: "gtm", name: "Sales / GTM", persona: null, mandate: "Pipeline health.", reads: ["deal_pipeline"] },
    { key: "chair", name: "Chair — overall",
      persona: "Paul Graham — make something people want", mandate: "Overall focus.",
      reads: ["deal_pipeline", "experiment_board"] },
  ],
};
const PANEL = {
  as_of: "2026-07-13",
  advisors: [{ key: "chair", name: "Chair — overall", persona: null, reflection: "Focus on one deal." }],
};

afterEach(() => vi.clearAllMocks());

describe("Advisory view", () => {
  it("renders a card per roster advisor, joining its reflection and persona", async () => {
    api.advisors.mockResolvedValue(ROSTER);
    api.advisory.mockResolvedValue(PANEL);
    render(<Advisory />);
    await screen.findByText("Sales / GTM");
    // chair has a persona badge and a reflection; gtm has neither yet
    expect(screen.getByText("as Paul Graham")).toBeInTheDocument();
    expect(screen.getByText("Focus on one deal.")).toBeInTheDocument();
    expect(screen.getAllByText(/no reflection yet/).length).toBe(1); // gtm
  });

  it("Reflect now starts the server-side background run", async () => {
    api.advisors.mockResolvedValue(ROSTER);
    api.advisory.mockResolvedValue({ as_of: null, advisors: [], generating: false, pending: [] });
    api.runAdvisory.mockResolvedValue({ started: true });
    render(<Advisory />);
    await screen.findByText("Sales / GTM");
    fireEvent.click(screen.getByRole("button", { name: /Reflect now/ }));
    await waitFor(() => expect(api.runAdvisory).toHaveBeenCalled());
  });

  it("while generating, shows 'reflecting…' for pending advisors and results as they land", async () => {
    api.advisors.mockResolvedValue(ROSTER);
    api.advisory.mockResolvedValue({
      as_of: "2026-07-13", generating: true, pending: ["chair"],
      advisors: [{ key: "gtm", name: "Sales / GTM", persona: null, reflection: "gtm landed" }],
    });
    render(<Advisory />);
    await screen.findByText("gtm landed");                        // gtm's reflection is in
    expect(screen.getByText(/reflecting…/)).toBeInTheDocument();  // chair still pending
    expect(screen.getByText(/leave and come back/)).toBeInTheDocument();
  });

  it("adds an advisor through the editor (id, name, mandate, reads)", async () => {
    api.advisors.mockResolvedValue(ROSTER);
    api.advisory.mockResolvedValue(PANEL);
    api.createAdvisor.mockResolvedValue({ advisor_id: "finance" });
    render(<Advisory />);
    await screen.findByText("Sales / GTM");
    fireEvent.click(screen.getByRole("button", { name: "+ Advisor" }));
    await screen.findByText("New advisor");
    fireEvent.change(screen.getByPlaceholderText(/e.g. finance/), { target: { value: "finance" } });
    fireEvent.change(screen.getByPlaceholderText(/Finance \/ Runway/), { target: { value: "Finance" } });
    fireEvent.change(screen.getByPlaceholderText(/what this advisor watches/), { target: { value: "Watch the runway." } });
    fireEvent.click(screen.getByText("funnel"));   // pick a read
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.createAdvisor).toHaveBeenCalled());
    const fields = api.createAdvisor.mock.calls[0][0];
    expect(fields).toMatchObject({ advisor_id: "finance", name: "Finance", reads: ["funnel"] });
  });

  it("edits an advisor's persona and can remove it (with confirm)", async () => {
    api.advisors.mockResolvedValue(ROSTER);
    api.advisory.mockResolvedValue(PANEL);
    api.updateAdvisor.mockResolvedValue({});
    api.removeAdvisor.mockResolvedValue({ removed: "chair", remaining: 1 });
    render(<Advisory />);
    await screen.findByText("Chair — overall");
    fireEvent.click(screen.getAllByTitle("edit advisor")[1]); // the chair
    await screen.findByText("Edit advisor");
    // remove requires a confirm step
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(api.removeAdvisor).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm remove" }));
    await waitFor(() => expect(api.removeAdvisor).toHaveBeenCalledWith("chair"));
  });
});
