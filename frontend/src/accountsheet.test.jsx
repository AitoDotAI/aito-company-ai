import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { AccountSheet, OverdueCommitments, StopChasing } from "./views.jsx";
import { api } from "./api.js";

// The CRO's account sheet and the two lists across accounts (docs/43 §7).
vi.mock("./api.js", () => ({ api: { accountSheet: vi.fn(), overdueCommitments: vi.fn(),
                                    unansweredAccounts: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

const FACT = (over) => ({
  fact_id: "sfa012", statement: "Budget cycle resets in Q1", kind: "attribute", slot: "budget_cycle",
  valid_from: "2026-10-26", author: "cro", source: { kind: "doc", id: "sdc009", status: "linked" },
  status: "active", touched_since: null, earlier: [], ...over,
});

const SHEET = (over) => ({
  company_id: "nakatomi-o",
  customer: { status: "no won deal on record", sources: [],
              qualifier: "direct deals only; indirect relationships are not shown yet" },
  latest_touch: { kind: "touch", id: "st1", date: "2026-11-02", channel: "call", direction: "out", outcome: "no_answer" },
  unanswered: { streak: 2, ended_by: null, unknown_before: "2026-06-04" },
  groups: [
    { kind: "attribute", slot: "budget_cycle",
      facts: [FACT({ touched_since: "touched since 2026-11-02" })] },
    { kind: "decision", slot: null,
      facts: [FACT({ fact_id: "sfa003", kind: "decision", slot: null, statement: "The new decision",
                     earlier: [FACT({ fact_id: "sfa011", kind: "decision", slot: null,
                                      statement: "The old decision", status: "superseded" })] })] },
  ],
  requests: [], ...over,
});

describe("the account sheet", () => {
  it("says the derived status with its direct-only qualifier, never 'not a customer'", async () => {
    api.accountSheet.mockResolvedValue(SHEET());
    render(<AccountSheet companyId="nakatomi-o" />);
    expect(await screen.findByText("no won deal on record")).toBeInTheDocument();
    expect(screen.getByText(/direct deals only; indirect relationships are not shown yet/)).toBeInTheDocument();
    expect(screen.queryByText(/not a customer/)).toBeNull();
    expect(api.accountSheet).toHaveBeenCalledWith("nakatomi-o");
  });

  it("shows the latest touch and the streak, and says where the count stops", async () => {
    api.accountSheet.mockResolvedValue(SHEET());
    render(<AccountSheet companyId="nakatomi-o" />);
    const line = await screen.findByTestId("sheet-touches");
    expect(line).toHaveTextContent("2026-11-02 · call · out · no_answer");
    expect(line).toHaveTextContent("2 unanswered in a row");
    expect(line).toHaveTextContent("streak unknown before 2026-06-04");
  });

  it("groups facts by slot, marks touched since as a pointer, and collapses earlier facts", async () => {
    api.accountSheet.mockResolvedValue(SHEET());
    render(<AccountSheet companyId="nakatomi-o" />);
    const row = (await screen.findByText("Budget cycle resets in Q1")).closest("li");
    expect(within(row).getByText("touched since 2026-11-02")).toBeInTheDocument();
    expect(within(row).getByText("active")).toBeInTheDocument();
    expect(screen.queryByText(/stale/i)).toBeNull();
    expect(screen.getByText("attribute/budget_cycle")).toBeInTheDocument();
    expect(screen.queryByText("The old decision")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "1 earlier" }));
    expect(screen.getByText("The old decision")).toBeInTheDocument();
  });

  it("cites the won deals when it is a customer", async () => {
    api.accountSheet.mockResolvedValue(SHEET({ customer: { status: "customer",
      sources: [{ kind: "deal", id: "sec015" }], qualifier: "direct deals only; indirect relationships are not shown yet" } }));
    render(<AccountSheet companyId="delos-ab" />);
    expect(await screen.findByText("customer")).toBeInTheDocument();
    expect(screen.getByText("deal:sec015")).toBeInTheDocument();
  });

  it("shows the error when the read fails", async () => {
    api.accountSheet.mockRejectedValue(new Error("no company with company_id or name 'x'"));
    render(<AccountSheet companyId="x" />);
    expect(await screen.findByText(/no company with company_id/)).toBeInTheDocument();
  });
});

describe("the lists across accounts", () => {
  it("lists overdue commitments with the day they were measured against", async () => {
    api.overdueCommitments.mockResolvedValue({ today: "2026-11-12", count: 1, requests: [], commitments: [
      { fact_id: "sfa007", company: "Nakatomi OÜ", company_id: "nakatomi-o", statement: "Send the pilot scope",
        due: "2026-11-09", days_overdue: 3, source: { kind: "mail", id: "m1", status: "external" } }] });
    render(<OverdueCommitments />);
    const row = (await screen.findByText("Send the pilot scope")).closest("tr");
    expect(within(row).getByText("2026-11-09")).toBeInTheDocument();
    expect(within(row).getByText("3 days")).toBeInTheDocument();
    expect(screen.getByText(/as of 2026-11-12 \(Helsinki\)/)).toBeInTheDocument();
  });

  it("lists the accounts to stop chasing, longest streak first", async () => {
    api.unansweredAccounts.mockResolvedValue({ min_streak: 3, count: 1, touches_without_account: 2, requests: [],
      accounts: [{ company_id: "strickland-gmbh", streak: 4, unknown_before: null,
                   ended_by: { date: "2026-11-01", outcome: "reply" },
                   latest_touch: { date: "2026-11-07", channel: "email" } }] });
    render(<StopChasing />);
    const row = (await screen.findByText("strickland-gmbh")).closest("tr");
    expect(within(row).getByText("4")).toBeInTheDocument();
    expect(within(row).getByText("2026-11-07")).toBeInTheDocument();
    expect(screen.getByText(/2 touches name no account/)).toBeInTheDocument();
    expect(api.unansweredAccounts).toHaveBeenCalledWith(3);
  });

  it("says so when nothing is overdue", async () => {
    api.overdueCommitments.mockResolvedValue({ today: "2026-11-12", count: 0, requests: [], commitments: [] });
    render(<OverdueCommitments />);
    expect(await screen.findByText("Nothing we owe is overdue.")).toBeInTheDocument();
  });
});
