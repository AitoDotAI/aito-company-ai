import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MyWork, UsersAdmin } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    myWork: vi.fn(), users: vi.fn(), assign: vi.fn(),
    me: vi.fn(), createUser: vi.fn(), updateUser: vi.fn(),
    tokens: vi.fn(), createToken: vi.fn(), revokeToken: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const MW = {
  user_id: "u_sdr", count: 2,
  contacts: [{ contact_id: "sc001", name: "Carol Lane", company: "Genco Oy", segment: "erp", tier: "A" }],
  deals: [{ deal_id: "d1", company: "Genco Oy", stage: "meeting", value_eur: 12000, probability: 40 }],
  todos: [],
};
const USERS = { users: [
  { user_id: "u_operator", name: "Alex Morgan", email: "alex@example.com", role: "operator", active: true },
  { user_id: "u_sdr", name: "Sam Rivera", email: "sam@example.com", role: "sdr", active: true },
] };

afterEach(() => vi.clearAllMocks());

describe("My work", () => {
  it("shows the leads and deals assigned to me with counts", async () => {
    api.myWork.mockResolvedValue(MW);
    api.users.mockResolvedValue(USERS);
    render(<MyWork />);
    await screen.findByText("Carol Lane");
    expect(screen.getByText("My leads")).toBeInTheDocument();
    expect(screen.getByText("My deals")).toBeInTheDocument();
    expect(screen.getAllByText("Genco Oy").length).toBeGreaterThan(0);   // lead + deal
    const selects = screen.getAllByTitle("assignee");
    expect(selects[0].value).toBe("u_sdr");
  });

  it("reassigning a lead calls api.assign", async () => {
    api.myWork.mockResolvedValue(MW);
    api.users.mockResolvedValue(USERS);
    api.assign.mockResolvedValue({});
    render(<MyWork />);
    await screen.findByText("Carol Lane");
    const sel = screen.getAllByTitle("assignee").find((s) => s.value === "u_sdr");
    fireEvent.change(sel, { target: { value: "u_operator" } });
    await waitFor(() => expect(api.assign).toHaveBeenCalled());
  });
});

describe("Admin (UsersAdmin)", () => {
  it("an SDR sees an operator-only message, no controls", async () => {
    api.me.mockResolvedValue({ role: "sdr", name: "Sam" });
    api.users.mockResolvedValue(USERS);
    render(<UsersAdmin />);
    await screen.findByText(/operator-only/);
    expect(screen.queryByRole("button", { name: /Add user/ })).not.toBeInTheDocument();
  });

  it("the operator can add a user and change a role", async () => {
    api.me.mockResolvedValue({ role: "operator", name: "Alex" });
    api.users.mockResolvedValue(USERS);
    api.tokens.mockResolvedValue({ tokens: [] });
    api.createUser.mockResolvedValue({ user_id: "u_new" });
    api.updateUser.mockResolvedValue({});
    render(<UsersAdmin />);
    await screen.findByText("Sam Rivera");
    // change Sam's role
    const roleSelects = screen.getAllByTitle("role");
    fireEvent.change(roleSelects[1], { target: { value: "operator" } });
    await waitFor(() => expect(api.updateUser).toHaveBeenCalledWith("u_sdr", { role: "operator" }));
    // add a user
    fireEvent.click(screen.getByRole("button", { name: /Add user/ }));
    fireEvent.change(screen.getByLabelText("name"), { target: { value: "Jo Lee" } });
    fireEvent.change(screen.getByLabelText("email"), { target: { value: "jo@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(api.createUser).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Jo Lee", email: "jo@example.com", role: "sdr" })));
  });

  it("creating an MCP token shows the secret once", async () => {
    api.me.mockResolvedValue({ role: "operator", name: "Alex" });
    api.users.mockResolvedValue(USERS);
    api.tokens.mockResolvedValue({ tokens: [
      { token_id: "tok1", label: "old one", prefix: "AbCdEf01", created: "2026-08-01", active: true }] });
    api.createToken.mockResolvedValue({ token_id: "tok2", label: "claude", prefix: "ZzYyXx99", token: "SECRET-PLAINTEXT-xyz" });
    render(<UsersAdmin />);
    await screen.findByText("Remote MCP tokens");
    expect(screen.getByText("old one")).toBeInTheDocument();
    expect(screen.getByText(/AbCdEf01/)).toBeInTheDocument();   // prefix shown, not full token
    fireEvent.click(screen.getByRole("button", { name: /New token/ }));
    fireEvent.change(screen.getByLabelText("label"), { target: { value: "claude" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.createToken).toHaveBeenCalledWith("claude"));
    // the plaintext is shown once, in the copy box
    expect(await screen.findByDisplayValue("SECRET-PLAINTEXT-xyz")).toBeInTheDocument();
  });
});
