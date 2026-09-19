// The right-side assistant: a chat over the bounded, Aito-backed tool loop
// (POST /api/assistant/chat). The agent reasons in the app, but every number
// it cites comes from a tool result — and we show the tool trace under each
// reply, which is what makes this double as a live MCP-contract tester.
//
// On desktop it's a resizable <aside> side panel. On phones it's a native
// <dialog> opened with showModal(): the browser renders it in the *top layer*,
// which is guaranteed to sit above everything and is immune to ancestor CSS
// (overflow, transform, stacking) — so the page can never show through behind
// the reply, which is what made the hand-rolled position:fixed overlay flaky.
import React, { useState, useRef, useEffect } from "react";
import { api } from "./api.js";
import { Markdown } from "./markdown.jsx";

const MIN_W = 320, MAX_W = 760, DEFAULT_W = 384;

// drag-to-resize the panel width, persisted across sessions (desktop only).
function useResizableWidth() {
  const [width, setWidth] = useState(() => {
    const saved = Number(localStorage.getItem("asst-width"));
    return saved >= MIN_W && saved <= MAX_W ? saved : DEFAULT_W;
  });
  function startResize(e) {
    e.preventDefault();
    const move = (ev) => {
      const w = Math.min(MAX_W, Math.max(MIN_W, window.innerWidth - ev.clientX));
      setWidth(w);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.style.userSelect = "";
      setWidth((w) => { localStorage.setItem("asst-width", String(w)); return w; });
    };
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
  return { width, startResize };
}

const isPhone = () => typeof window !== "undefined" && window.innerWidth <= 720;

const SUGGESTIONS = [
  "How's my pipeline?",
  "Who should I call at 12:15?",
  "What did yesterday change?",
  "Which experiments are paying off?",
];

function Trace({ trace }) {
  if (!trace?.length) return null;
  return (
    <div className="trace">
      {trace.map((t, i) => (
        <span key={i} className={"chip" + (t.ok ? "" : " bad")}
              title={t.error || JSON.stringify(t.args)}>
          {t.tool}{Object.keys(t.args || {}).length ? "(…)" : "()"}{t.ok ? "" : " ✕"}
        </span>
      ))}
    </div>
  );
}

// The reusable chat core: the message list + composer + one bounded tool-loop
// turn with a Stop. Driven by a conversation's {msgs, setMsgs} — the right-side
// Assistant panel and the full-page Chat view both render it. Key it by the
// conversation id at the call site so switching threads gives it clean state.
export function ChatThread({ msgs, setMsgs }) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const bodyRef = useRef(null);
  const abortRef = useRef(null);   // the in-flight request's AbortController

  // abort a dangling request if this unmounts (thread switch / panel close)
  useEffect(() => () => abortRef.current?.abort(), []);

  // Keep the newest message in view — scroll the message list itself, never the
  // window (scrollIntoView would scroll an ancestor).
  useEffect(() => {
    const b = bodyRef.current;
    if (b) b.scrollTop = b.scrollHeight;
  }, [msgs, busy]);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput(""); setErr(null);
    const history = [...msgs, { role: "user", content: q }];
    setMsgs(history); setBusy(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const wire = history.map(({ role, content }) => ({ role, content }));
      const res = await api.assistant(wire, ctrl.signal);
      if (abortRef.current !== ctrl) return;   // stopped or superseded — drop it
      setMsgs([...history, { role: "assistant", content: res.reply, trace: res.trace }]);
    } catch (e) {
      if (abortRef.current !== ctrl) return;   // aborted — not a real error
      setMsgs(history); // keep the question; let them retry
      if (e.name !== "AbortError") setErr(e.message);
    } finally {
      if (abortRef.current === ctrl) { abortRef.current = null; setBusy(false); }
    }
  }

  // Stop the in-flight turn: abort the request and go idle immediately. The
  // question stays so it's one tap to resend. (A read-only turn already running
  // server-side simply finishes and is ignored.)
  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
  }

  return (
    <>
      <div className="asst-body" ref={bodyRef}>
        {msgs.length === 0 && (
          <div className="asst-hint">
            <p>Ask about the pipeline, the funnels, who to call, the experiments.
               Answers are grounded in Aito — every number comes from a tool call,
               shown beneath each reply.</p>
            <div className="suggests">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggest" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          // NB: the reply role class must NOT be "assistant" — that collides with
          // the .assistant panel/overlay CSS and turns each reply bubble into a
          // fixed full-screen overlay on mobile. Use "bot".
          <div key={i} className={"bubble " + (m.role === "assistant" ? "bot" : m.role)}>
            {m.role === "assistant"
              ? <><Markdown text={m.content} /><Trace trace={m.trace} /></>
              : m.content}
          </div>
        ))}
        {busy && <div className="bubble bot"><span className="dots">querying Aito…</span></div>}
        {err && <div className="error">Assistant error: {err}</div>}
      </div>

      <form className="asst-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Ask the system…" disabled={busy} />
        {busy
          ? <button type="button" className="asst-stop" onClick={stop} title="stop">Stop</button>
          : <button type="submit" disabled={!input.trim()}>Send</button>}
      </form>
    </>
  );
}

// The right-side panel (desktop <aside>, phone <dialog>) — a wrapper around
// ChatThread with the header actions. The conversation and "New chat" are owned
// by App (the shared conversations store), so both survive closing the dialog.
export function Assistant({ onClose, msgs, setMsgs, onNew }) {
  const dialogRef = useRef(null);
  const { width, startResize } = useResizableWidth();
  const phone = isPhone();

  // Phones: promote the <dialog> into the browser's top layer.
  useEffect(() => {
    const d = dialogRef.current;
    if (phone && d && !d.open) { try { d.showModal(); } catch { /* jsdom has no showModal */ } }
  }, [phone]);

  const inner = (
    <>
      {!phone && <div className="asst-resize" onPointerDown={startResize} title="drag to resize" />}
      <div className="asst-head">
        <span className="asst-title"><span className="pulse" /> Assistant</span>
        <div className="asst-actions">
          {msgs.length > 0 && onNew && (
            <button className="asst-new" onClick={onNew}
                    title="start a new conversation">New chat</button>
          )}
          <button className="asst-x" onClick={onClose} title="close">×</button>
        </div>
      </div>
      <ChatThread msgs={msgs} setMsgs={setMsgs} />
    </>
  );

  if (phone) {
    return (
      <dialog className="asst-modal" ref={dialogRef}
              onCancel={(e) => { e.preventDefault(); onClose(); }}>
        {inner}
      </dialog>
    );
  }
  return (
    <aside className="assistant" style={{ "--asst-w": width + "px" }}>
      {inner}
    </aside>
  );
}
