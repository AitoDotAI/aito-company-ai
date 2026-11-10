import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { FactLedger, NoteFacts } from "./views.jsx";
import { api } from "./api.js";

// The fact ledger (docs/43): every fact as a row, listed rather than drawn;
// a source id narrows the list to the facts that cite that record; and a
// note lists the facts taken from it.
vi.mock("./api.js", () => ({ api: { factLedger: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

const ROW = (over) => ({
  fact_id: "sfa012", company: "Nakatomi OÜ", company_id: "nakatomi-o", kind: "attribute",
  slot: "budget_cycle", statement: "Budget cycle resets in Q1", author: "cro",
  valid_from: "2026-10-26", source: { kind: "doc", id: "sdc009", status: "linked" },
  status: "active", ...over,
});

describe("the fact ledger", () => {
  it("lists each fact with its account, predicate, source and status", async () => {
    api.factLedger.mockResolvedValue({ count: 2, requests: [], facts: [
      ROW(),
      ROW({ fact_id: "sfa011", kind: "decision", slot: null, statement: "Decision expected from the founder",
            source: { kind: "call", id: "call-seed-1001", status: "external" }, status: "superseded" }),
    ] });
    render(<FactLedger />);
    const row = (await screen.findByText("Budget cycle resets in Q1")).closest("tr");
    expect(within(row).getByText("Nakatomi OÜ")).toBeInTheDocument();
    expect(within(row).getByText("attribute/budget_cycle")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "doc:sdc009" })).toBeInTheDocument();
    expect(within(row).getByText("active")).toBeInTheDocument();
    const old = screen.getByText("Decision expected from the founder").closest("tr");
    expect(within(old).getByText("decision")).toBeInTheDocument();
    expect(within(old).getByText("superseded")).toBeInTheDocument();
    expect(api.factLedger).toHaveBeenCalledWith({ company: "", kind: "", status: "", source_id: "" });
  });

  it("narrows to the facts that cite a record when its id is clicked", async () => {
    api.factLedger.mockResolvedValue({ count: 1, requests: [], facts: [ROW()] });
    render(<FactLedger />);
    fireEvent.click(await screen.findByRole("button", { name: "doc:sdc009" }));
    await waitFor(() => expect(api.factLedger).toHaveBeenLastCalledWith(
      { company: "", kind: "", status: "", source_id: "sdc009" }));
    expect(screen.getByLabelText("record id")).toHaveValue("sdc009");
  });

  it("filters by status, and shows a review status as it is", async () => {
    api.factLedger.mockResolvedValue({ count: 1, requests: [], facts: [
      ROW({ status: "review: source changed" })] });
    render(<FactLedger />);
    expect(await screen.findByText("review: source changed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("status"), { target: { value: "review: source changed" } });
    await waitFor(() => expect(api.factLedger).toHaveBeenLastCalledWith(
      { company: "", kind: "", status: "review: source changed", source_id: "" }));
  });

  it("lists a derived customer status with every won deal it rests on", async () => {
    api.factLedger.mockResolvedValue({ count: 1, requests: [], facts: [
      ROW({ fact_id: "derived-customer-acme-o", company: "Acme OÜ", company_id: "acme-o", kind: "derived",
            slot: "customer_status", author: "derived", status: "derived", valid_from: "2026-01-29",
            statement: "Customer: 2 won deals on record (direct deals only; indirect relationships are not shown yet)",
            source: { kind: "deal", id: "sec016", status: "linked" },
            sources: [{ kind: "deal", id: "sec016", status: "linked" }, { kind: "deal", id: "sec054", status: "linked" }] }),
    ] });
    render(<FactLedger />);
    const row = (await screen.findByText(/Customer: 2 won deals on record/)).closest("tr");
    expect(within(row).getByText("derived/customer_status")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "deal:sec016" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "deal:sec054" })).toBeInTheDocument();
    expect(within(row).getByText("derived")).toBeInTheDocument();
    expect(within(screen.getByLabelText("kind")).getByRole("option", { name: "derived" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("status")).getByRole("option", { name: "derived" })).toBeInTheDocument();
  });

  it("shows the error when the read fails", async () => {
    api.factLedger.mockRejectedValue(new Error("unknown status 'stale'"));
    render(<FactLedger />);
    expect(await screen.findByText(/unknown status 'stale'/)).toBeInTheDocument();
  });
});

describe("a note's facts", () => {
  it("lists the facts that cite this document", async () => {
    api.factLedger.mockResolvedValue({ count: 1, requests: [], facts: [ROW()] });
    render(<NoteFacts docId="sdc009" />);
    expect(await screen.findByText("Facts from this note")).toBeInTheDocument();
    expect(screen.getByText("Budget cycle resets in Q1")).toBeInTheDocument();
    expect(api.factLedger).toHaveBeenCalledWith({ source_id: "sdc009" });
  });

  it("says so when no fact cites the note", async () => {
    api.factLedger.mockResolvedValue({ count: 0, requests: [], facts: [] });
    render(<NoteFacts docId="sdc001" />);
    expect(await screen.findByText("No facts cite this note yet.")).toBeInTheDocument();
  });
});
