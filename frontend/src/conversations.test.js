import { describe, it, expect, vi } from "vitest";

// the store syncs to /api/chats; here the server is "offline" so localStorage
// (the store's local state) is authoritative — exactly the fallback path.
vi.mock("./api.js", () => ({ api: {
  chatsList: () => Promise.reject(new Error("offline")),
  chatSave: () => Promise.resolve({}),
  chatRemove: () => Promise.resolve({}),
} }));

import { conversations } from "./conversations.js";

// The store is a module singleton, so these operate relative to current state.
describe("conversations store", () => {
  it("creates, titles from the first user message, selects, and removes", () => {
    const before = conversations.get().threads.length;
    const id = conversations.create();
    expect(conversations.active().id).toBe(id);
    expect(conversations.get().threads.length).toBe(before + 1);

    // the title derives from the first user message
    conversations.setMsgs(id, [{ role: "user", content: "How's my pipeline today?" }]);
    expect(conversations.active().title).toMatch(/How's my pipeline/);

    // create another, switch back
    const other = conversations.create();
    expect(conversations.active().id).toBe(other);
    conversations.select(id);
    expect(conversations.active().id).toBe(id);

    // remove
    conversations.remove(id);
    expect(conversations.get().threads.find((t) => t.id === id)).toBeUndefined();
    conversations.remove(other);
  });

  it("never drops below one thread", () => {
    conversations.get().threads.slice().forEach((t) => conversations.remove(t.id));
    expect(conversations.get().threads.length).toBeGreaterThanOrEqual(1);
    expect(conversations.active()).toBeTruthy();
  });
});
