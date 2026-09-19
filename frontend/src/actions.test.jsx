import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ActionPipeline, WeekCalendar } from "./primitives.jsx";

function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const TODOS = [
  { todo_id: "a", title: "Alpha", priority: 1, status: "ready", prep_status: "n_a" },
  { todo_id: "b", title: "Bravo", priority: 2, status: "ready", prep_status: "n_a" },
  { todo_id: "c", title: "Charlie", priority: 3, status: "ready", prep_status: "n_a" },
];

describe("ActionPipeline — Trello-like row affordances", () => {
  it("marks an item done inline without opening a dialog", () => {
    const onDone = vi.fn();
    render(<ActionPipeline todos={TODOS} onDone={onDone} onEdit={() => {}} />);
    // each row has a mark-done control; click the first
    fireEvent.click(screen.getAllByTitle("mark done")[0]);
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "a" }));
  });

  it("the edit pen triggers edit (and does not also fire done)", () => {
    const onEdit = vi.fn();
    const onDone = vi.fn();
    render(<ActionPipeline todos={TODOS} onEdit={onEdit} onDone={onDone} />);
    fireEvent.click(screen.getAllByTitle("edit")[1]);
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "b" }));
    expect(onDone).not.toHaveBeenCalled();
  });

  it("tapping anywhere on the row opens the editor (mobile-friendly hit area)", () => {
    const onEdit = vi.fn();
    const onDone = vi.fn();
    render(<ActionPipeline todos={TODOS} onEdit={onEdit} onDone={onDone} />);
    fireEvent.click(screen.getByText("Charlie")); // the title, not the little pencil
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "c" }));
    expect(onDone).not.toHaveBeenCalled();
  });

  it("does not make the row a tap target when it isn't editable (no onEdit)", () => {
    const { container } = render(<ActionPipeline todos={TODOS} onDone={() => {}} />);
    expect(container.querySelector(".arow.editable")).toBeNull();
  });

  it("drag-reorder persists the new order (one reorder call with the new ids)", () => {
    const onReorder = vi.fn();
    const { container } = render(
      <ActionPipeline todos={TODOS} onReorder={onReorder} onEdit={() => {}} onDone={() => {}} />);
    const rows = container.querySelectorAll(".arow");
    // drag the 3rd row (Charlie) onto the 1st position
    fireEvent.dragStart(rows[2]);
    fireEvent.dragOver(rows[0]);
    fireEvent.drop(rows[0]);
    expect(onReorder).toHaveBeenCalledWith(["c", "a", "b"]);
  });

  it("is not draggable when no onReorder is given (e.g. the Now lens)", () => {
    const { container } = render(<ActionPipeline todos={TODOS} onEdit={() => {}} />);
    expect(container.querySelector(".arow.draggable")).toBeNull();
  });

  // a small helper: run a touch swipe across a row from startX to endX
  function swipe(row, startX, endX) {
    fireEvent.touchStart(row, { touches: [{ clientX: startX, clientY: 50 }] });
    fireEvent.touchMove(row, { touches: [{ clientX: endX, clientY: 52 }] });
    fireEvent.touchEnd(row, { changedTouches: [{ clientX: endX, clientY: 52 }] });
  }

  it("swipe right marks done, swipe left archives (touch)", () => {
    const onDone = vi.fn();
    const onArchive = vi.fn();
    const { container } = render(
      <ActionPipeline todos={TODOS} onEdit={() => {}} onDone={onDone} onArchive={onArchive} />);
    const rows = container.querySelectorAll(".arow");
    swipe(rows[0], 200, 360);   // right, past threshold → done
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "a" }));
    swipe(rows[1], 200, 40);    // left, past threshold → archive
    expect(onArchive).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "b" }));
  });

  it("a short swipe snaps back and fires nothing", () => {
    const onDone = vi.fn();
    const onArchive = vi.fn();
    const { container } = render(
      <ActionPipeline todos={TODOS} onEdit={() => {}} onDone={onDone} onArchive={onArchive} />);
    swipe(container.querySelectorAll(".arow")[0], 200, 230);  // 30px < threshold
    expect(onDone).not.toHaveBeenCalled();
    expect(onArchive).not.toHaveBeenCalled();
  });

  it("a mouse interaction does not swipe (leaves click/drag-reorder alone)", () => {
    const onDone = vi.fn();
    const onArchive = vi.fn();
    const { container } = render(
      <ActionPipeline todos={TODOS} onEdit={() => {}} onDone={onDone} onArchive={onArchive} />);
    const row = container.querySelectorAll(".arow")[0];
    // mouse drag fires no touch events, so the swipe never engages
    fireEvent.mouseDown(row, { clientX: 200 });
    fireEvent.mouseMove(row, { clientX: 40 });
    fireEvent.mouseUp(row, { clientX: 40 });
    expect(onDone).not.toHaveBeenCalled();
    expect(onArchive).not.toHaveBeenCalled();
  });
});

describe("WeekCalendar — week grid for the calendar lens", () => {
  function thisWeek(dow) { // a date in the current week at the given weekday (1=Mon..7=Sun)
    const d = new Date(); d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + (dow - 1));
    return ymd(d);
  }

  it("places a scheduled todo in its day with its time slot, ordered by time", () => {
    const day = thisWeek(2); // Tuesday this week
    const todos = [
      { todo_id: "late", title: "Afternoon call", priority: 2, due_date: day, slot: "15:30" },
      { todo_id: "early", title: "Morning call", priority: 1, due_date: day, slot: "09:00" },
    ];
    const { container } = render(<WeekCalendar todos={todos} onEdit={() => {}} />);
    const items = [...container.querySelectorAll(".wc-item .wc-t")].map((e) => e.textContent);
    // both shown, earlier slot first
    expect(items).toEqual(["Morning call", "Afternoon call"]);
    expect(screen.getByText("09:00")).toBeInTheDocument();
  });

  it("clicking a calendar chip opens the editor", () => {
    const onEdit = vi.fn();
    const todos = [{ todo_id: "x", title: "Ship post", priority: 1, due_date: thisWeek(3), slot: "10:00" }];
    render(<WeekCalendar todos={todos} onEdit={onEdit} />);
    fireEvent.click(screen.getByText("Ship post"));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ todo_id: "x" }));
  });

  it("prev/next walks weeks (a this-week item drops off when paged forward)", () => {
    const todos = [{ todo_id: "x", title: "Ship post", priority: 1, due_date: thisWeek(3), slot: "10:00" }];
    render(<WeekCalendar todos={todos} onEdit={() => {}} />);
    expect(screen.getByText("Ship post")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("next week"));
    expect(screen.queryByText("Ship post")).not.toBeInTheDocument(); // not in next week
    fireEvent.click(screen.getByText("today"));                      // back to this week
    expect(screen.getByText("Ship post")).toBeInTheDocument();
  });
});
