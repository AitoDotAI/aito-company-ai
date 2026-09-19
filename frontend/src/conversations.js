// A shared store for the assistant's conversations. localStorage is the instant
// / offline cache; the server (chats.py, /api/chats) is the durable source of
// truth, so history survives a cache-clear and shows on any device. One store
// (useSyncExternalStore) so the full-page Chat view and the quick ✦ panel stay
// in sync.
//
// Shape: { active: <id>, threads: [{ id, title, msgs, updated }] }, newest
// first. `title` is derived from the first user message. Writes update
// localStorage immediately and push to the server best-effort (retried while a
// thread stays dirty); a failed/offline server just leaves localStorage in
// charge until the next flush.
import { useSyncExternalStore } from "react";
import { api } from "./api.js";

const KEY = "asst-conversations";
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const now = () => Date.now();

function freshThread() {
  return { id: uid(), title: "New chat", msgs: [], updated: now() };
}

function initial() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (s && Array.isArray(s.threads) && s.threads.length &&
        s.threads.some((t) => t.id === s.active)) return s;
  } catch { /* ignore malformed/absent */ }
  const t = freshThread();
  return { active: t.id, threads: [t] };
}

let state = initial();
const subs = new Set();
const dirty = new Set();   // thread ids whose server write is pending/failed

function commit(next) {
  state = next;
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode */ }
  subs.forEach((f) => f());
}

function titleFor(msgs) {
  const first = msgs.find((m) => m.role === "user");
  if (!first) return "New chat";
  const t = first.content.trim();
  return t.length > 42 ? t.slice(0, 42) + "…" : t;
}

// ---- server sync (best-effort; never throws into the caller) ----
function push(id) {
  const t = state.threads.find((x) => x.id === id);
  if (!t) return;
  dirty.add(id);
  Promise.resolve(api.chatSave?.(id, { title: t.title, msgs: t.msgs, updated: t.updated }))
    .then((r) => { if (r) dirty.delete(id); })
    .catch(() => { /* stays dirty; retried by flush */ });
}
function flush() { [...dirty].forEach(push); }
function pushRemove(id) {
  Promise.resolve(api.chatRemove?.(id)).catch(() => { /* best-effort */ });
}

async function hydrate() {
  let server;
  try { server = (await api.chatsList()).conversations || []; }
  catch { return; }   // offline / no endpoint: localStorage stands
  const byId = new Map(server.map((c) => [c.id, c]));
  // keep any local thread that has content but isn't on the server yet, and
  // push it up so it's saved too
  const localExtra = state.threads.filter((t) => t.msgs?.length && !byId.has(t.id));
  let threads = [...server, ...localExtra];
  threads.sort((a, b) => (b.updated || 0) - (a.updated || 0));
  if (!threads.length) threads = [freshThread()];
  const active = threads.some((t) => t.id === state.active) ? state.active : threads[0].id;
  commit({ active, threads });
  localExtra.forEach(push);
  flush();
}

hydrate();
if (typeof window !== "undefined") window.addEventListener("online", flush);

export const conversations = {
  subscribe(f) { subs.add(f); return () => subs.delete(f); },
  get() { return state; },
  active() { return state.threads.find((t) => t.id === state.active) || state.threads[0]; },
  select(id) { if (id !== state.active && state.threads.some((t) => t.id === id)) commit({ ...state, active: id }); },
  create() {
    const t = freshThread();
    commit({ active: t.id, threads: [t, ...state.threads] });
    push(t.id);
    return t.id;
  },
  remove(id) {
    let threads = state.threads.filter((t) => t.id !== id);
    if (!threads.length) threads = [freshThread()];
    const active = state.active === id ? threads[0].id : state.active;
    commit({ active, threads });
    pushRemove(id);
  },
  // replace a thread's messages (send() calls this as the turn progresses)
  setMsgs(id, msgs) {
    commit({ ...state, threads: state.threads.map((t) =>
      t.id === id ? { ...t, msgs, title: titleFor(msgs), updated: now() } : t) });
    push(id);
  },
};

export function useConversations() {
  return useSyncExternalStore(conversations.subscribe, conversations.get, conversations.get);
}
