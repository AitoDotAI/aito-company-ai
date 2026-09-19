import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Routines } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: { routines: vi.fn(), tickRoutine: vi.fn(), prepareRoutine: vi.fn(),
         runRoutine: vi.fn(), createRoutine: vi.fn(), updateRoutine: vi.fn() },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const ROWS = {
  routines: [
    { routine_id: "r1", title: "Fill La Growth Machine", area: "sales", cadence: "weekly",
      weekday: "mon", prep: "prospects", due: true, overdue: true, days_overdue: 3, notes: "" },
    { routine_id: "r2", title: "Monthly bookkeeping", area: "operations", cadence: "monthly",
      day_of_month: 1, prep: "none", due: false, overdue: false, days_overdue: 0, last_done: "2026-06-02" },
  ],
};

afterEach(() => vi.clearAllMocks());

describe("Routines view", () => {
  it("shows due/overdue state and a cadence label", async () => {
    api.routines.mockResolvedValue(ROWS);
    render(<Routines />);
    await screen.findByText("Fill La Growth Machine");
    expect(screen.getByText(/overdue 3d/)).toBeInTheDocument();
    expect(screen.getByText("weekly · mon")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument(); // r2 not due
  });

  it("ticks a routine done without a dialog", async () => {
    api.routines.mockResolvedValue(ROWS);
    api.tickRoutine.mockResolvedValue({});
    render(<Routines />);
    await screen.findByText("Fill La Growth Machine");
    fireEvent.click(screen.getAllByTitle("mark done for this period")[0]);
    await waitFor(() => expect(api.tickRoutine).toHaveBeenCalledWith("r1"));
  });

  it("tapping the row opens the editor; the ✓ and Prepare buttons don't", async () => {
    api.routines.mockResolvedValue(ROWS);
    render(<Routines />);
    await screen.findByText("Fill La Growth Machine");
    // tap the title → editor opens
    fireEvent.click(screen.getByText("Fill La Growth Machine"));
    await screen.findByText("Edit routine");
    // the inline ✓ stops propagation: it ticks, it does not open the editor
    api.tickRoutine.mockResolvedValue({});
    fireEvent.click(screen.getByText("Cancel")); // close the editor first
    fireEvent.click(screen.getAllByTitle("mark done for this period")[0]);
    await waitFor(() => expect(api.tickRoutine).toHaveBeenCalledWith("r1"));
    expect(screen.queryByText("Edit routine")).not.toBeInTheDocument();
  });

  it("Prepare shows the Aito candidates + a copyable Claude prompt", async () => {
    api.routines.mockResolvedValue(ROWS);
    api.prepareRoutine.mockResolvedValue({
      candidates: [{ contact_id: "c1", company: "Acme Oy", "$p": 0.42 }],
      prompt: "Prepare the next outreach batch… call opener_context(c1)…",
    });
    render(<Routines />);
    await screen.findByText("Fill La Growth Machine");
    fireEvent.click(screen.getByRole("button", { name: /Prepare/ }));
    await screen.findByText(/Prepare — Fill La Growth Machine/);
    expect(screen.getByText("Acme Oy")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/opener_context/)).toBeInTheDocument(); // the prompt textarea
  });

  it("Run executes the routine and shows the narration (every routine, even not-due)", async () => {
    api.routines.mockResolvedValue(ROWS);
    api.runRoutine.mockResolvedValue({
      routine_id: "r2", title: "Monthly bookkeeping", ran: true,
      reply: "Reconciled June: 3 invoices open, nothing overdue.",
      document_id: "dc_x", tool_calls: 2, rounds: 3,
    });
    render(<Routines />);
    await screen.findByText("Monthly bookkeeping");
    // r2 has prep "none" (no Prepare button) but Run is offered for every routine
    const runButtons = screen.getAllByRole("button", { name: /Run ▶/ });
    fireEvent.click(runButtons[runButtons.length - 1]); // r2's Run
    await waitFor(() => expect(api.runRoutine).toHaveBeenCalledWith("r2"));
    await screen.findByText(/Ran — Monthly bookkeeping/);
    expect(screen.getByText(/Reconciled June/)).toBeInTheDocument();
    expect(screen.getByText(/2 tool calls, 3 rounds/)).toBeInTheDocument();
  });
});
