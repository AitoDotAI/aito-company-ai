import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatView } from "./views.jsx";

// ChatView needs the assistant endpoint; the conversations store also syncs to
// /api/chats — stub those so it runs offline (localStorage in charge).
vi.mock("./api.js", () => ({ api: {
  assistant: vi.fn(),
  chatsList: () => Promise.reject(new Error("offline")),
  chatSave: () => Promise.resolve({}),
  chatRemove: () => Promise.resolve({}),
}, pct: (x) => x }));

describe("Chat view", () => {
  it("is chat-first, opens a history list, and + New chat adds a thread", () => {
    const { container } = render(<ChatView />);
    // chat-first: the composer is visible, with a Chats(n) history button
    expect(screen.getByPlaceholderText(/Ask the system/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Chats \(/ }));   // open history
    const before = container.querySelectorAll(".chat-row").length;
    fireEvent.click(screen.getByRole("button", { name: "+ New chat" }));  // back to chat
    expect(screen.getByPlaceholderText(/Ask the system/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Chats \(/ }));   // reopen history
    expect(container.querySelectorAll(".chat-row").length).toBe(before + 1);
  });

  it("deletes a conversation only after a confirm (two taps)", () => {
    const { container } = render(<ChatView />);
    fireEvent.click(screen.getByRole("button", { name: "+ New" }));  // ensure ≥2 threads
    fireEvent.click(screen.getByRole("button", { name: /Chats \(/ }));
    const before = container.querySelectorAll(".chat-row").length;
    const del = container.querySelector(".chat-row .ct-del");
    fireEvent.click(del);                                    // arms ("remove?")
    expect(container.querySelectorAll(".chat-row").length).toBe(before); // nothing gone yet
    fireEvent.click(container.querySelector(".chat-row .ct-del.confirm")); // confirms
    expect(container.querySelectorAll(".chat-row").length).toBe(before - 1);
  });
});
