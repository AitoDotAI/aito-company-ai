import { describe, it, expect, vi, afterEach } from "vitest";
import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Assistant } from "./assistant.jsx";
import { api } from "./api.js";

// Mock the api module so the component's api.assistant is a controllable
// vi.fn (no real fetch — jsdom can't resolve the relative /api URL anyway).
vi.mock("./api.js", () => ({ api: { assistant: vi.fn() } }));

afterEach(() => { vi.clearAllMocks(); localStorage.clear(); });

// The conversation now lives in App; a small harness owns that state for tests.
// onNew clears (App wires it to conversations.create()).
function Harness() {
  const [msgs, setMsgs] = useState([]);
  return <Assistant onClose={() => {}} msgs={msgs} setMsgs={setMsgs}
                    onNew={() => setMsgs([])} />;
}

describe("Assistant chat panel", () => {
  it("sends the conversation and renders the grounded reply + tool trace", async () => {
    api.assistant.mockResolvedValue({
      reply: "You have 15 open deals.",
      trace: [{ tool: "deal_pipeline", args: {}, ok: true }],
      rounds: 2,
    });
    render(<Harness />);

    fireEvent.change(screen.getByPlaceholderText(/Ask the system/i), {
      target: { value: "How's my pipeline?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    // the user's message shows immediately
    expect(screen.getByText("How's my pipeline?")).toBeInTheDocument();
    // the reply and the tool-trace chip arrive
    await screen.findByText("You have 15 open deals.");
    expect(screen.getByText(/deal_pipeline/)).toBeInTheDocument();

    // the server got role/content only (no system prompt from the client)
    // role/content only (no system prompt from the client); a 2nd arg is the AbortSignal
    expect(api.assistant).toHaveBeenCalledWith(
      [{ role: "user", content: "How's my pipeline?" }], expect.anything());
  });

  it("surfaces an error and keeps the question for retry", async () => {
    api.assistant.mockRejectedValue(new Error("no Azure OpenAI key"));
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText(/Ask the system/i), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await screen.findByText(/Assistant error: no Azure OpenAI key/);
    expect(screen.getByText("hi")).toBeInTheDocument(); // question retained
  });

  it("Stop cancels an in-flight request and keeps the question", async () => {
    // a request that never resolves on its own — only Stop ends the wait
    api.assistant.mockReturnValue(new Promise(() => {}));
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText(/Ask the system/i), { target: { value: "slow one" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText(/querying Aito/);          // busy
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    // back to idle: the question stays, the busy indicator is gone, Send returns
    expect(screen.getByText("slow one")).toBeInTheDocument();
    expect(screen.queryByText(/querying Aito/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("offers suggestion chips before any conversation", () => {
    render(<Harness />);
    expect(screen.getByText("How's my pipeline?")).toBeInTheDocument();
    expect(screen.getByText("Who should I call at 12:15?")).toBeInTheDocument();
  });

  it("New chat clears the conversation and brings back the suggestions", async () => {
    api.assistant.mockResolvedValue({ reply: "You have 15 open deals.", trace: [], rounds: 1 });
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText(/Ask the system/i), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("You have 15 open deals.");
    // "New chat" shows once there are messages; clicking it resets
    fireEvent.click(screen.getByRole("button", { name: /New chat/ }));
    expect(screen.queryByText("You have 15 open deals.")).not.toBeInTheDocument();
    expect(screen.getByText("Who should I call at 12:15?")).toBeInTheDocument(); // suggestions back
  });

  it("is resizable: a persisted in-range width is applied as the width var", () => {
    localStorage.setItem("asst-width", "520");
    const { container } = render(<Harness />);
    expect(container.querySelector(".asst-resize")).toBeInTheDocument();
    expect(container.querySelector(".assistant").style.getPropertyValue("--asst-w")).toBe("520px");
  });

  it("ignores an out-of-bounds persisted width and falls back to the default", () => {
    localStorage.setItem("asst-width", "99999");
    const { container } = render(<Harness />);
    expect(container.querySelector(".assistant").style.getPropertyValue("--asst-w")).toBe("384px");
  });

  it("marks a failed tool call in the trace", async () => {
    api.assistant.mockResolvedValue({
      reply: "That window isn't valid.",
      trace: [{ tool: "who_to_call", args: { window: "midnight" }, ok: false, error: "unknown window" }],
      rounds: 2,
    });
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText(/Ask the system/i), {
      target: { value: "call at midnight" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const chip = await screen.findByText(/who_to_call/);
    expect(chip).toHaveClass("bad");
  });
});
