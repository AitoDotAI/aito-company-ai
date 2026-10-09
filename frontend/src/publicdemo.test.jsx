// A public demo (docs/33) refuses every write server-side with a 403. These
// pin the UI half: it does not OFFER what can only fail, nor show views a
// guest cannot read (the raw-table routes are operator-only by design).
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TabbedView } from "./App.jsx";
import { QuickAdd } from "./views.jsx";
import { setPublicDemo } from "./session.js";

vi.mock("./api.js", () => ({
  api: { todoOptions: vi.fn(() => new Promise(() => {})), table: vi.fn(() => new Promise(() => {})) },
  pct: (x) => (x == null ? "–" : Math.round(x * 100) + "%"),
}));

afterEach(() => setPublicDemo(false));

const view = {
  tabs: [
    { id: "todo", label: "To do", render: () => <div>todo</div> },
    { id: "posts", label: "Posts", operatorOnly: true, render: () => <div>posts</div> },
    { id: "analytics", label: "Analytics", render: () => <div>analytics</div> },
  ],
  data: [{ table: "posts" }],
};
const labels = () => screen.getAllByRole("button").map((b) => b.textContent);

describe("public demo", () => {
  it("normally shows every tab, the Data sheets included", () => {
    render(<TabbedView view={view} />);
    expect(labels()).toEqual(["To do", "Posts", "Analytics", "Data"]);
  });

  it("hides operator-only tabs and the Data sheets from a visitor", () => {
    setPublicDemo(true);
    render(<TabbedView view={view} />);
    expect(labels()).toEqual(["To do", "Analytics"]);
  });

  it("offers no add row, because nothing can be added", () => {
    setPublicDemo(true);
    const { container } = render(<QuickAdd defaultArea="sales" />);
    expect(container).toBeEmptyDOMElement();
  });
});
