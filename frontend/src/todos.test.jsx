import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TodoEditor, QuickAdd } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    todoOptions: vi.fn(),
    createTodo: vi.fn(),
    updateTodo: vi.fn(),
    completeTodo: vi.fn(),
    archiveTodo: vi.fn(),
    classifyTodo: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const OPTIONS = {
  areas: ["experiments", "marketing", "operations", "rnd", "sales"],
  action_types: ["admin", "call", "email", "meeting", "none", "post", "research"],
  statuses: ["ready", "draft", "prog", "done"],
  prep_statuses: ["n_a", "ready", "prep_needed"],
  calendar_areas: ["marketing", "sales"],
  contacts: [{ id: "c1", name: "Mika", company: "Globex" }],
  deals: [{ id: "d1", company: "Globex", stage: "demo" }],
};

afterEach(() => vi.clearAllMocks());

async function openEditor(props) {
  api.todoOptions.mockResolvedValue(OPTIONS);
  render(<TodoEditor onClose={() => {}} onSaved={() => {}} {...props} />);
  await screen.findByText(props.todo ? "Edit action" : "New action");
}

describe("TodoEditor", () => {
  it("creates a todo with the typed/selected fields (operations catch-all)", async () => {
    api.createTodo.mockResolvedValue({ todo_id: "t1" });
    await openEditor({ todo: null, defaultArea: "operations" });

    fireEvent.change(screen.getByPlaceholderText(/Call Globex/), { target: { value: "Renew TLS cert" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createTodo).toHaveBeenCalled());
    const fields = api.createTodo.mock.calls[0][0];
    expect(fields.area).toBe("operations");
    expect(fields.title).toBe("Renew TLS cert");
    expect(fields.priority).toBe(2);
    expect(fields.linked_type).toBe("");   // no deal chosen
  });

  it("hides due/window for a pipeline area, shows them for a calendar area", async () => {
    await openEditor({ todo: null, defaultArea: "operations" });
    expect(screen.queryByText("due")).not.toBeInTheDocument();
    // switch to a calendar area → the due field appears
    fireEvent.change(screen.getByDisplayValue("operations"), { target: { value: "sales" } });
    expect(await screen.findByText("due")).toBeInTheDocument();
  });

  it("on edit, sends only the changed fields", async () => {
    api.updateTodo.mockResolvedValue({});
    const todo = { todo_id: "t9", area: "sales", title: "Call Globex", action_type: "call",
                   priority: 3, status: "ready", prep_status: "ready", due_date: "2026-06-25",
                   window: "fri_1430", stakeholder_id: "c1", linked_type: "deal", linked_id: "d1" };
    await openEditor({ todo });

    fireEvent.change(screen.getByDisplayValue("3"), { target: { value: "1" } }); // priority 3→1
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateTodo).toHaveBeenCalled());
    const [id, changes] = api.updateTodo.mock.calls[0];
    expect(id).toBe("t9");
    expect(changes).toEqual({ priority: 1 });   // only the diff
  });

  it("mark done calls completeTodo", async () => {
    api.completeTodo.mockResolvedValue({ todo: {}, deal: null });
    await openEditor({ todo: { todo_id: "t9", area: "operations", title: "x", priority: 2,
                               status: "ready", prep_status: "n_a" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark done" }));
    await waitFor(() => expect(api.completeTodo).toHaveBeenCalledWith("t9"));
  });

  it("Archive calls archiveTodo (abandon, advances nothing)", async () => {
    api.archiveTodo.mockResolvedValue({ todo: { status: "archived" } });
    await openEditor({ todo: { todo_id: "t9", area: "operations", title: "x", priority: 2,
                               status: "ready", prep_status: "n_a" } });
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(api.archiveTodo).toHaveBeenCalledWith("t9"));
  });

  it("Suggest fills the blank fields from Aito (operator then confirms)", async () => {
    api.classifyTodo.mockResolvedValue({
      title: "Ship the positioning post",
      suggest: { area: { top: { value: "marketing", p: 0.94 } },
                 action_type: { top: { value: "post", p: 0.93 } } },
      stakeholders: [],
    });
    api.createTodo.mockResolvedValue({ todo_id: "t2" });
    await openEditor({ todo: null, defaultArea: "operations" });

    fireEvent.change(screen.getByPlaceholderText(/Call Globex/), { target: { value: "Ship the positioning post" } });
    fireEvent.click(screen.getByRole("button", { name: /Suggest fields/ }));

    // the suggested values populate, with confidence hints shown
    await screen.findByText("Aito 94%");
    expect(screen.getByDisplayValue("marketing")).toBeInTheDocument();
    expect(screen.getByDisplayValue("post")).toBeInTheDocument();

    // confirm → create uses the suggested-then-confirmed fields
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.createTodo).toHaveBeenCalled());
    const fields = api.createTodo.mock.calls[0][0];
    expect(fields.area).toBe("marketing");
    expect(fields.action_type).toBe("post");
  });

  it("surfaces a save error and stays open", async () => {
    api.createTodo.mockRejectedValue(new Error("open sales todo needs a due_date"));
    await openEditor({ todo: null, defaultArea: "sales" });
    fireEvent.change(screen.getByPlaceholderText(/Call Globex/), { target: { value: "Call X" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await screen.findByText(/Save error: open sales todo needs a due_date/);
  });
});

describe("QuickAdd (embedded, debounced inference)", () => {
  async function mount(defaultArea = "operations") {
    api.todoOptions.mockResolvedValue(OPTIONS);
    const onAdded = vi.fn();
    render(<QuickAdd defaultArea={defaultArea} onAdded={onAdded} />);
    await screen.findByPlaceholderText(/Add an action/);
    return onAdded;
  }

  it("auto-classifies after you stop typing and sets the inferred area", async () => {
    api.classifyTodo.mockResolvedValue({
      suggest: { area: { top: { value: "sales", p: 0.91 } },
                 action_type: { top: { value: "call", p: 0.88 } } },
      stakeholders: [{ id: "c1", name: "Bob Stone", company: "Acme" }],
    });
    await mount("operations");
    fireEvent.change(screen.getByPlaceholderText(/Add an action/), { target: { value: "Call Bob at Acme" } });

    // the debounced classify fires and the inference line appears
    const line = await screen.findByText(/Aito:/);
    expect(line).toHaveTextContent("sales");          // inferred area, shown
    expect(line).toHaveTextContent("matched Bob Stone");
    expect(api.classifyTodo).toHaveBeenCalledWith("Call Bob at Acme", {});
  });

  it("creates on Enter with the inferred + visible fields, then resets", async () => {
    api.classifyTodo.mockResolvedValue({
      suggest: { area: { top: { value: "sales", p: 0.9 } }, action_type: { top: { value: "call", p: 0.9 } } },
      stakeholders: [{ id: "c1", name: "Bob Stone", company: "Acme" }],
    });
    api.createTodo.mockResolvedValue({ todo_id: "t1" });
    const onAdded = await mount("operations");

    const input = screen.getByPlaceholderText(/Add an action/);
    fireEvent.change(input, { target: { value: "Call Bob at Acme" } });
    await screen.findByText(/Aito:/);                 // inference applied
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(api.createTodo).toHaveBeenCalled());
    const fields = api.createTodo.mock.calls[0][0];
    expect(fields.area).toBe("sales");                // inferred
    expect(fields.action_type).toBe("call");          // inferred (hidden)
    expect(fields.stakeholder_id).toBe("c1");          // auto-matched
    expect(fields.due_date).toBeTruthy();              // calendar area → date defaulted
    expect(onAdded).toHaveBeenCalled();
    expect(input.value).toBe("");                      // reset for the next add
  });

  it("a calendar-area quick-add includes the time slot", async () => {
    api.classifyTodo.mockResolvedValue({ suggest: {}, stakeholders: [] });
    api.createTodo.mockResolvedValue({ todo_id: "t3" });
    await mount("marketing");   // a calendar area → slot field shows
    const input = screen.getByPlaceholderText(/Add an action/);
    fireEvent.change(input, { target: { value: "Ship the launch post" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(api.createTodo).toHaveBeenCalled());
    const fields = api.createTodo.mock.calls[0][0];
    expect(fields.area).toBe("marketing");
    expect(fields.slot).toMatch(/^\d\d:\d\d$/);   // HH:MM slot sent
    expect(fields.due_date).toBeTruthy();
  });

  it("a manual area choice is not overridden by inference", async () => {
    api.classifyTodo.mockResolvedValue({
      suggest: { area: { top: { value: "sales", p: 0.9 } } }, stakeholders: [],
    });
    await mount("operations");
    // choose rnd before typing
    fireEvent.change(screen.getAllByTitle("type")[0], { target: { value: "rnd" } });
    fireEvent.change(screen.getByPlaceholderText(/Add an action/), { target: { value: "benchmark the db" } });
    await screen.findByText(/Aito:/);
    expect(screen.getAllByTitle("type")[0].value).toBe("rnd");   // stayed rnd
  });
});

describe("TodoEditor detail (regression: detail was dropped/empty)", () => {
  it("pre-fills the existing detail and saves an edit", async () => {
    api.updateTodo.mockResolvedValue({});
    await openEditor({ todo: {
      todo_id: "sd1", area: "sales", title: "Call Globex", priority: 1,
      status: "ready", prep_status: "n_a",
      detail: "Longer note\nsecond line\nthird line",
    }});
    const ta = screen.getByPlaceholderText(/longer description/i);
    expect(ta.value).toContain("second line");   // shows, not blank
    fireEvent.change(ta, { target: { value: "Updated detail" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(api.updateTodo).toHaveBeenCalled());
    expect(api.updateTodo.mock.calls[0][1].detail).toBe("Updated detail");
  });
});
