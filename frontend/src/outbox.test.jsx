import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Outbox } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: { outbox: vi.fn(), updateOutbox: vi.fn(), decideOutbox: vi.fn() },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const ROW = {
  outbox_id: "ob-1", status: "staged", channel: "email",
  to: "pia@example.com", cc: null, contact_name: "Pia Virtanen", company: "Globex",
  subject: "Re: pilot scope", body: "Hi Pia,\n\nHere is the scope.\n",
  thread_id: "thr-77", reply_to_message_id: "msg-104",
  send_after: "2026-08-18T08:00:00", class: "re_entry", agent: "cro",
  rationale: "Thread went quiet after the meeting; scope was the open item.",
  created: "2026-08-15T09:00:00", updated: "2026-08-15T09:00:00",
  message_id: null, sent_at: null, result: null,
};
const NEW_THREAD = {
  ...ROW, outbox_id: "ob-2", contact_name: "Olli Mäki", company: "Initech",
  to: "olli@example.com", subject: "Predictive layer",
  body: "Olli,\n\nOne question about your supplier rows.\n",
  thread_id: null, reply_to_message_id: null,
  class: "first_touch", rationale: "No prior thread; their AI announcement is the trigger.",
};
const QUEUE = { count: 2, counts: { staged: 2 }, rows: [ROW, NEW_THREAD] };

afterEach(() => vi.clearAllMocks());

describe("Outbox approval view", () => {
  it("shows what a decision needs: who, why, when, and the full text", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    expect(screen.getByText("Pia Virtanen · Globex")).toBeInTheDocument();
    expect(screen.getByText(/Thread went quiet/)).toBeInTheDocument();
    expect(screen.getByText(/Here is the scope/)).toBeInTheDocument();
    expect(screen.getByText(/to pia@example.com/)).toBeInTheDocument();
    // it opens on the staged queue — the only status that needs a person
    expect(api.outbox).toHaveBeenCalledWith("staged");
  });

  it("flags whether the message replies on a thread or starts a new one", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    expect(screen.getByText("↩ in thread")).toBeInTheDocument();
    expect(screen.getByText("new thread")).toBeInTheDocument();
  });

  it("approves in one tap and refetches", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    api.decideOutbox.mockResolvedValue({ ...ROW, status: "approved" });
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(api.decideOutbox).toHaveBeenCalledWith("ob-1", "approved"));
    await waitFor(() => expect(api.outbox).toHaveBeenCalledTimes(2));
  });

  it("strikes in one tap", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    api.decideOutbox.mockResolvedValue({ ...ROW, status: "struck" });
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    fireEvent.click(screen.getAllByRole("button", { name: "Strike" })[0]);
    await waitFor(() => expect(api.decideOutbox).toHaveBeenCalledWith("ob-1", "struck"));
  });

  it("edits the text before approving", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    api.updateOutbox.mockResolvedValue({ ...ROW, subject: "Re: pilot scope (revised)" });
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await screen.findByText("Edit message");
    fireEvent.change(screen.getByDisplayValue("Re: pilot scope"),
                     { target: { value: "Re: pilot scope (revised)" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateOutbox).toHaveBeenCalled());
    expect(api.updateOutbox.mock.calls[0][0]).toBe("ob-1");
    expect(api.updateOutbox.mock.calls[0][1]).toMatchObject({
      subject: "Re: pilot scope (revised)", class: "re_entry",
    });
  });

  it("a decided message shows its status instead of the buttons", async () => {
    api.outbox.mockResolvedValue(
      { count: 1, counts: { approved: 1 }, rows: [{ ...ROW, status: "approved" }] });
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByText("approved")).toBeInTheDocument();
  });

  it("surfaces a refused decision rather than pretending it landed", async () => {
    api.outbox.mockResolvedValue(QUEUE);
    api.decideOutbox.mockRejectedValue(new Error("operator only"));
    render(<Outbox />);
    await screen.findByText("Re: pilot scope");
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await screen.findByText("operator only");
  });
});
