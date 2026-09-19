import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { VIEWS, Documents } from "./views.jsx";
import { api } from "./api.js";

vi.mock("./api.js", () => ({
  api: {
    documents: vi.fn(), createDocument: vi.fn(), updateDocument: vi.fn(),
    deleteDocument: vi.fn(), todoOptions: vi.fn(),
  },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

const DOCS = {
  count: 2,
  documents: [
    { doc_id: "dc1", title: "Ideal customer profile", body: "# ICP\nNordic B2B SaaS.",
      kind: "internal", area: "sales", company_eff: null, contact_name: null, updated: "2026-06-02" },
    { doc_id: "dc2", title: "Genco account plan", body: "# Genco\nPilot on invoicing.",
      kind: "internal", area: "sales", company_eff: "Genco Oy", contact_name: "Carol Lane",
      updated: "2026-06-18" },
  ],
};

const OPTS = { contacts: [{ id: "sc001", name: "Carol Lane", company: "Genco Oy" }] };

function setViewport(isPhone) {
  window.matchMedia = (query) => ({
    matches: isPhone, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  });
}

afterEach(() => { vi.clearAllMocks(); setViewport(false); });

describe("Documents view", () => {
  it("lists documents with kind/area/link badges and shows the first in the pane", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    render(VIEWS.documents.render());
    await screen.findByText("Genco account plan");
    // badges: kind + area + linked company/person
    expect(screen.getAllByText("internal").length).toBeGreaterThan(0);
    expect(screen.getByText("Genco Oy")).toBeInTheDocument();
    expect(screen.getByText("Carol Lane")).toBeInTheDocument();
    // the first doc's body renders in the pane by default (desktop)
    expect(screen.getByText(/Nordic B2B SaaS/)).toBeInTheDocument();
  });

  it("clicking a document swaps the reading pane", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    render(VIEWS.documents.render());
    await screen.findByText("Genco account plan");
    fireEvent.click(screen.getByText("Genco account plan"));
    expect(screen.getByText(/Pilot on invoicing/)).toBeInTheDocument();
  });

  it("the kind filter re-queries with that kind", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    render(VIEWS.documents.render());
    await screen.findByText("Ideal customer profile");
    fireEvent.click(screen.getByRole("button", { name: "docs" }));
    await waitFor(() =>
      expect(api.documents).toHaveBeenCalledWith(expect.objectContaining({ kind: "docs" })));
  });

  it("shows a visible Edit control that opens the pane's doc and updates it in place", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    api.todoOptions.mockResolvedValue(OPTS);
    api.updateDocument.mockResolvedValue({ doc_id: "dc1" });
    render(VIEWS.documents.render());
    await screen.findByText("Ideal customer profile");
    // the edit affordance is a labelled, discoverable button (not an invisible pen)
    fireEvent.click(screen.getByRole("button", { name: /✎ Edit/ }));
    // the editor opens pre-loaded with the pane's active doc (dc1)
    await screen.findByText("Edit document");
    expect(screen.getByLabelText("title").value).toBe("Ideal customer profile");
    fireEvent.change(screen.getByLabelText("body"), { target: { value: "# ICP\nrevised" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateDocument).toHaveBeenCalledWith(
      "dc1", expect.objectContaining({ body: "# ICP\nrevised" })));
  });

  it("New document opens the editor and creates via the API", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    api.todoOptions.mockResolvedValue(OPTS);
    api.createDocument.mockResolvedValue({ doc_id: "dc9" });
    render(VIEWS.documents.render());
    await screen.findByText("Ideal customer profile");
    fireEvent.click(screen.getByRole("button", { name: /New document/ }));
    await screen.findByText("New document");
    fireEvent.change(screen.getByLabelText("title"), { target: { value: "Playbook" } });
    fireEvent.change(screen.getByLabelText("body"), { target: { value: "# Playbook\nlead with churn" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.createDocument).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Playbook", kind: "internal" })));
  });
});

describe("Documents (area-locked tab)", () => {
  it("filters to the area, hides the area chips, and locks the editor's area", async () => {
    setViewport(false);
    api.documents.mockResolvedValue(DOCS);
    api.todoOptions.mockResolvedValue(OPTS);
    render(<Documents area="sales" />);
    // queried with the locked area
    await waitFor(() =>
      expect(api.documents).toHaveBeenCalledWith(expect.objectContaining({ area: "sales" })));
    await screen.findByText("Genco account plan");
    // area filter chips are not offered when the area is locked
    expect(screen.queryByRole("button", { name: "any area" })).not.toBeInTheDocument();
    // the editor's area select is disabled (locked to the tab's area)
    fireEvent.click(screen.getByRole("button", { name: /New document/ }));
    await screen.findByText("New document");
    expect(screen.getByLabelText("area")).toBeDisabled();
  });
});
