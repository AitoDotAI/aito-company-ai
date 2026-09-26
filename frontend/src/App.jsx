// App shell: the fixed information architecture from rev 3 §1.2
// (Now · Work · Knowledge · Analytics), a hash-routed view area, and the
// agent-status footer. Views are composed from primitives in views.jsx.
import React, { useEffect, useState } from "react";
import { VIEWS, ScopedData, Documents, QuickFind } from "./views.jsx";
import { Assistant } from "./assistant.jsx";
import { conversations, useConversations } from "./conversations.js";
import { api } from "./api.js";

const NAV = [
  { group: "NOW", items: [["now", "Today"], ["overview", "Overview"], ["mywork", "My work"], ["chat", "Chat"], ["routines", "Routines"]] },
  { group: "WORK", items: [["sales", "Sales"], ["marketing", "Marketing"], ["events", "Events"], ["ops", "Operations"], ["rnd", "R&D"], ["exp", "Learning"]] },
  { group: "KNOWLEDGE", items: [["graph", "Knowledge graph"], ["search", "Search"], ["activity", "Activity"], ["documents", "Documents"]] },
  { group: "ANALYTICS", items: [["salesanalytics", "Sales analytics"], ["analytics", "Metrics"], ["decisions", "Decisions"], ["data", "Data"]] },
  { group: "ADMIN", items: [["admin", "Admin"]] },
];

// A view's content, behind a tab strip. A view either declares its own `tabs`
// (named panels — the Sales view splits Pipeline / Companies / Calls / Funnel so
// no single tab crowds a phone), or falls back to one implicit "Overview" tab.
// A "Data" tab (the raw rows behind the view) is appended when the view declares
// `data` specs. Remounts per route (the parent's key={route}), so the active tab
// resets on navigation. With a single tab, the strip is hidden.
export function TabbedView({ view, param }) {
  const base = view.tabs || [{ id: "overview", label: "Overview", render: () => view.render(param) }];
  // an area view gets a Documents tab (docs/25) filtered to its area — the
  // playbooks and plans sit beside the pipeline, same generic seam as Data.
  const withDocs = view.docsArea
    ? [...base, { id: "documents", label: "Documents", render: () => <Documents area={view.docsArea} /> }]
    : base;
  const tabs = view.data
    ? [...withDocs, { id: "data", label: "Data", render: () => <ScopedData specs={view.data} /> }]
    : withDocs;
  const [tab, setTab] = useState(tabs[0].id);
  if (tabs.length === 1) return tabs[0].render();
  const active = tabs.find((t) => t.id === tab) || tabs[0];
  return (
    <>
      <div className="tabs">
        {tabs.map((t) => (
          <button key={t.id} className={"tab" + (t.id === tab ? " active" : "")}
                  onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      {active.render()}
    </>
  );
}

function useHashRoute(fallback) {
  const read = () => window.location.hash.replace(/^#\/?/, "") || fallback;
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [route, (r) => { window.location.hash = "/" + r; }];
}

const isPhone = () => typeof window !== "undefined" && window.innerWidth <= 720;

// ?bare=1 — render the view alone, with no sidebar and no assistant panel.
// Those two take ~40% of the width and say nothing about what the product
// does, which makes every screenshot and embed smaller than it needs to be.
const isBare = () => typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).has("bare");

export default function App() {
  const [route, go] = useHashRoute("now");
  const bare = isBare();
  // the assistant is open by default on desktop; on phones it starts closed so
  // the view owns the small screen (open it with the ✦ toggle). Closing persists.
  const [chat, setChat] = useState(
    () => !isBare() && !isPhone() && localStorage.getItem("asst-open") !== "false");
  useEffect(() => { localStorage.setItem("asst-open", chat ? "true" : "false"); }, [chat]);
  // conversations live in a shared store (conversations.js) so the quick panel
  // here and the full-page Chat view operate on the same threads. The panel
  // shows the active thread; "New chat" starts another.
  useConversations();                      // re-render on any thread change
  const active = conversations.active();
  // who's signed in (Entra Easy Auth identity, resolved to a user + role)
  const [me, setMe] = useState(null);
  useEffect(() => { api.me().then(setMe).catch(() => {}); }, []);
  // the nav is a fixed sidebar on desktop; on phones it's an off-canvas drawer
  const [navOpen, setNavOpen] = useState(false);
  // desktop: the sidebar can be collapsed away to hand its width to the editor
  // (e.g. take notes on half the screen while a video call has the other half).
  const [navCollapsed, setNavCollapsed] = useState(
    () => isBare() || localStorage.getItem("nav-collapsed") === "true");
  useEffect(() => { localStorage.setItem("nav-collapsed", navCollapsed ? "true" : "false"); }, [navCollapsed]);
  const [viewKey, ...restSeg] = route.split("/");   // "documents/dc1" → key + param
  const param = restSeg.join("/") || null;
  const view = VIEWS[viewKey] || VIEWS.now;
  const navTo = (id) => { go(id); setNavOpen(false); };
  return (
    <div className={"app" + (chat && route !== "chat" ? " with-chat" : "")
                   + (navCollapsed ? " nav-collapsed" : "") + (bare ? " bare" : "")}>
      {/* mobile-only top bar: drawer toggle · brand · assistant toggle */}
      <header className="topbar">
        <button className="tb-btn" aria-label="menu" onClick={() => setNavOpen(true)}>☰</button>
        <span className="tb-brand"><span className="dot" /> Company AI</span>
        {route !== "chat" && (
          <span className="tb-actions">
            {viewKey !== "note" && (
              <button className="tb-btn" aria-label="new note" onClick={() => navTo("note")}>＋</button>
            )}
            {!chat && (
              <button className="tb-btn ask" aria-label="assistant" onClick={() => setChat(true)}>✦</button>
            )}
          </span>
        )}
      </header>

      {/* desktop: slim tab to bring the collapsed sidebar back */}
      <button className="nav-reopen" aria-label="show navigation" title="show navigation"
              onClick={() => setNavCollapsed(false)}>»</button>

      {navOpen && <div className="nav-backdrop" onClick={() => setNavOpen(false)} />}
      <nav className={"side" + (navOpen ? " open" : "")}>
        <div className="nav-brand">
          <span className="dot" />
          <div>
            <div className="nm">Company AI</div>
            <div className="sb">{me ? `${me.name}${me.role ? " · " + me.role : ""}` : "Aito"}</div>
          </div>
          <button className="nav-collapse" aria-label="collapse navigation"
                  title="collapse navigation" onClick={() => setNavCollapsed(true)}>«</button>
        </div>
        {NAV.map((g) => (
          <div className="nav-group" key={g.group}>
            <div className="gl">{g.group}</div>
            {g.items.map(([id, label]) => (
              <button key={id} className={"nav-item" + (viewKey === id ? " active" : "")}
                      onClick={() => navTo(id)}>
                {label}
                {VIEWS[id] && !VIEWS[id].prims && <span className="badge">soon</span>}
              </button>
            ))}
          </div>
        ))}
        <div className="nav-agent">
          <span className="pulse" /> agent reads the same data via MCP
        </div>
      </nav>

      <main>
        <div className="view-head">
          <div>
            <h1>{view.title}</h1>
            <div className="desc">{view.desc}</div>
          </div>
          {route !== "chat" && (
            <div className="head-actions">
              <QuickFind />
              {viewKey !== "note" && (
                <button className="note-btn" onClick={() => navTo("note")}>＋ Note</button>
              )}
              {!chat && (
                <button className="ask-btn" onClick={() => setChat(true)}>
                  <span className="pulse" /> Ask
                </button>
              )}
            </div>
          )}
        </div>
        {view.prims && (
          <div className="composed">
            <span className="lbl">composed of</span>
            {view.prims.map((p) => <span className="prim-tag" key={p}>{p}</span>)}
          </div>
        )}
        <div className="view" key={route}><TabbedView view={view} param={param} /></div>
      </main>

      {chat && route !== "chat" && (
        <Assistant key={active.id} onClose={() => setChat(false)}
                   msgs={active.msgs}
                   setMsgs={(m) => conversations.setMsgs(active.id, m)}
                   onNew={() => conversations.create()} />
      )}
    </div>
  );
}
