import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NoteCreate } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    todoOptions: vi.fn(),
    classifyDocument: vi.fn(),
    documentContext: vi.fn(),
    createDocument: vi.fn(),
    updateDocument: vi.fn(),
    createCompany: vi.fn(),
    createContact: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

afterEach(() => { vi.clearAllMocks(); localStorage.clear(); });

// the three async helpers most tests don't exercise return empty by default
function stubIdle() {
  api.classifyDocument.mockResolvedValue({ companies: [], contacts: [], topics: [] });
  api.documentContext.mockResolvedValue({ same_company: [], similar: [] });
}

describe("NoteCreate (Aito-inferred note)", () => {
  it("infers company + person from the title and files the note", async () => {
    api.todoOptions.mockResolvedValue({
      contacts: [{ id: "sc1", name: "Robin Aalto", company: "Acme" }],
    });
    api.classifyDocument.mockResolvedValue({
      companies: [{ company_id: "acme", name: "Acme" }],
      contacts: [{ id: "sc1", name: "Robin Aalto", company: "Acme" }],
      topics: ["meeting"],
    });
    api.documentContext.mockResolvedValue({
      same_company: [{ doc_id: "dc9", title: "Acme", noted_on: null }],
      similar: [],
    });
    api.createDocument.mockResolvedValue({ doc_id: "dcNew" });

    render(<NoteCreate />);
    await screen.findByPlaceholderText(/Acme meeting note/i);
    fireEvent.change(screen.getByPlaceholderText(/Acme meeting note/i),
                     { target: { value: "Acme meeting note" } });

    // the debounced inference fires and pre-fills company + shows the inference line
    await waitFor(() => expect(api.classifyDocument).toHaveBeenCalledWith("Acme meeting note", {}));
    await screen.findByText(/Aito:/);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    // the graph's context (same-company prior notes) shows up
    await waitFor(() => expect(api.documentContext).toHaveBeenCalled());

    // fill the body and save — the inferred fields flow into createDocument
    fireEvent.change(screen.getByPlaceholderText(/Heading/), { target: { value: "Talked pricing." } });
    fireEvent.click(screen.getByText("Save note"));
    await waitFor(() => expect(api.createDocument).toHaveBeenCalled());
    // saving ensures the company entity exists so the link never dangles
    expect(api.createCompany).toHaveBeenCalledWith("Acme");
    const payload = api.createDocument.mock.calls[0][0];
    expect(payload.title).toBe("Acme meeting note");
    expect(payload.company).toBe("Acme");
    expect(payload.stakeholder_id).toBe("sc1");
    expect(payload.noted_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("keeps the saved note on screen and UPDATES it on the next save (no fork)", async () => {
    api.todoOptions.mockResolvedValue({ contacts: [] });
    stubIdle();
    api.createDocument.mockResolvedValue({ doc_id: "dcNew" });
    api.updateDocument.mockResolvedValue({ doc_id: "dcNew" });

    render(<NoteCreate />);
    const title = await screen.findByPlaceholderText(/Acme meeting note/i);
    fireEvent.change(title, { target: { value: "Meeting" } });
    fireEvent.change(screen.getByPlaceholderText(/Heading/), { target: { value: "notes" } });

    fireEvent.click(screen.getByText("Save note"));
    await waitFor(() => expect(api.createDocument).toHaveBeenCalledTimes(1));

    // the note stays on screen (title not cleared) and an Open link appears
    expect(title.value).toBe("Meeting");
    await screen.findByText("Open ↗");

    // editing again and saving UPDATES dcNew rather than creating a second doc
    fireEvent.change(screen.getByPlaceholderText(/Heading/), { target: { value: "notes + more" } });
    fireEvent.click(await screen.findByText("Save changes"));
    await waitFor(() => expect(api.updateDocument).toHaveBeenCalledWith("dcNew", expect.objectContaining({ body: "notes + more" })));
    expect(api.createDocument).toHaveBeenCalledTimes(1);   // still just the one
  });

  it("autosaves a draft and recovers it on remount", async () => {
    api.todoOptions.mockResolvedValue({ contacts: [] });
    stubIdle();

    const { unmount } = render(<NoteCreate />);
    const title = await screen.findByPlaceholderText(/Acme meeting note/i);
    fireEvent.change(title, { target: { value: "Long meeting" } });
    fireEvent.change(screen.getByPlaceholderText(/Heading/), { target: { value: "an hour of notes" } });

    // the debounced autosave lands in localStorage (the inference/context
    // effects re-arm the debounce, so allow a little slack over the 700ms delay)
    await waitFor(() => expect(JSON.parse(localStorage.getItem("note-draft") || "null")?.f?.body)
      .toBe("an hour of notes"), { timeout: 3000 });

    // simulate a crash / closed tab, then reopen the note view
    unmount();
    render(<NoteCreate />);
    const title2 = await screen.findByPlaceholderText(/Acme meeting note/i);
    expect(title2.value).toBe("Long meeting");
    expect(screen.getByPlaceholderText(/Heading/).value).toBe("an hour of notes");
    await screen.findByText(/Recovered an unsaved draft/i);
  });

  it("adds a new company inline and selects it on the note", async () => {
    api.todoOptions.mockResolvedValue({ contacts: [] });
    stubIdle();
    api.createCompany.mockResolvedValue({ company_id: "novaco", name: "NovaCo", created: true });

    render(<NoteCreate />);
    await screen.findByPlaceholderText(/Acme meeting note/i);
    // open the "＋ New" next to company (there are two — company is the first)
    fireEvent.click(screen.getAllByRole("button", { name: "＋ New" })[0]);
    await screen.findByText("New company");
    fireEvent.change(screen.getByLabelText("name"), { target: { value: "NovaCo" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createCompany).toHaveBeenCalledWith("NovaCo"));
    // the note's company field now carries the created company
    await waitFor(() => expect(screen.getByPlaceholderText("e.g. Acme").value).toBe("NovaCo"));
  });

  it("adds a new person inline, refetches options, and selects them", async () => {
    api.todoOptions
      .mockResolvedValueOnce({ contacts: [] })                                   // initial
      .mockResolvedValue({ contacts: [{ id: "cNew", name: "Dana Fox", company: "NovaCo" }] }); // after add
    stubIdle();
    api.createContact.mockResolvedValue({ id: "cNew", name: "Dana Fox", company: "NovaCo" });

    render(<NoteCreate />);
    await screen.findByPlaceholderText(/Acme meeting note/i);
    fireEvent.click(screen.getAllByRole("button", { name: "＋ New" })[1]);       // person's + New
    await screen.findByText("New person");
    fireEvent.change(screen.getByLabelText("name"), { target: { value: "Dana Fox" } });
    // "company" labels both the note field and the modal field — the modal's is last
    fireEvent.change(screen.getAllByLabelText("company").at(-1), { target: { value: "NovaCo" } });
    fireEvent.change(screen.getByLabelText("role"), { target: { value: "CTO" } });
    fireEvent.click(screen.getByRole("button", { name: "Create person" }));

    await waitFor(() => expect(api.createContact).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Dana Fox", company: "NovaCo", role: "CTO",
        segment: "other", tier: "C", ai_lifecycle: "none", source: "cold" })));
    // options refetch and the new person is selected on the note
    await waitFor(() => expect(screen.getByText("Dana Fox · NovaCo")).toBeInTheDocument());
  });

  it("is in the view registry as its own view", async () => {
    const { VIEWS } = await import("./views.jsx");
    expect(VIEWS.note).toBeTruthy();
    expect(VIEWS.note.title).toBe("New note");
  });
});
