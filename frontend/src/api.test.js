import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, pct } from "./api.js";

// Capture the URL each call fetches, and control the response.
let lastUrl;
function mockFetch(body, ok = true, status = 200) {
  lastUrl = undefined;
  global.fetch = vi.fn(async (url) => {
    lastUrl = url;
    return { ok, status, json: async () => body };
  });
}

beforeEach(() => mockFetch({ ok: true }));
afterEach(() => vi.restoreAllMocks());

describe("api query-string building", () => {
  it("drops null/empty params (so /todos with no area has no query)", async () => {
    await api.todos("now");
    expect(lastUrl).toBe("/api/todos?lens=now");
    await api.todos("calendar", "sales");
    expect(lastUrl).toBe("/api/todos?lens=calendar&area=sales");
  });

  it("a no-arg call sends no query string", async () => {
    await api.deals();
    expect(lastUrl).toBe("/api/deals");
  });

  it("table(name) sends just the name; table(name, where) JSON-encodes the filter", async () => {
    await api.table("deals");
    expect(lastUrl).toBe("/api/table?name=deals");
    await api.table("todos", { area: "operations" });
    // URLSearchParams encodes the JSON; decode to compare the intent
    const q = new URL("http://x" + lastUrl.slice(4)).searchParams;
    expect(q.get("name")).toBe("todos");
    expect(JSON.parse(q.get("where"))).toEqual({ area: "operations" });
  });

  it("spreads a slice into funnel params", async () => {
    await api.funnel("website", { segment: "erp" });
    const q = new URL("http://x" + lastUrl.slice(4)).searchParams;
    expect(q.get("name")).toBe("website");
    expect(q.get("segment")).toBe("erp");
  });

  it("builds the documents query with filters", async () => {
    await api.documents({ kind: "internal", area: "sales" });
    const q = new URL("http://x" + lastUrl).searchParams;
    expect(lastUrl.startsWith("/api/documents?")).toBe(true);
    expect(q.get("kind")).toBe("internal");
    expect(q.get("area")).toBe("sales");
  });
});

describe("api error surfacing", () => {
  it("throws the backend's {error} message", async () => {
    mockFetch({ error: "failed to open 'experiments'" });
    await expect(api.experiments()).rejects.toThrow("failed to open 'experiments'");
  });

  it("throws on a non-ok response without an error body", async () => {
    mockFetch({}, false, 500);
    await expect(api.deals()).rejects.toThrow("HTTP 500");
  });

  it("returns the parsed body on success", async () => {
    mockFetch({ total: 3, derived: true });
    await expect(api.decisions()).resolves.toEqual({ total: 3, derived: true });
  });
});

describe("pct", () => {
  it("formats a fraction as a rounded percentage", () => {
    expect(pct(0.49)).toBe("49%");
    expect(pct(1)).toBe("100%");
    expect(pct(0)).toBe("0%");
  });
  it("renders a dash for null/undefined", () => {
    expect(pct(null)).toBe("–");
    expect(pct(undefined)).toBe("–");
  });
});
