// The views, composed from primitives. Each Work view opens with its
// action block per rev 3 — but the todos/deals/library tables aren't built
// yet, so those blocks show an honest "not wired" placeholder rather than
// fabricated data (the repo's weak-and-honest rule). The analytics surfaces
// we *can* back with Aito today are fully live.
import React, { useState, useEffect, useRef } from "react";
import { api, pct } from "./api.js";
import { Block, KpiRow, FunnelChart, QuarterBars, WhyList, Levers, BarRow, Select,
         ActionPipeline, ActionCalendar, WeekCalendar, useAsync, useIsPhone, Loading, ErrorBox } from "./primitives.jsx";
import { Markdown } from "./markdown.jsx";
import { ChatThread } from "./assistant.jsx";
import { conversations, useConversations } from "./conversations.js";

function Placeholder({ needs }) {
  return (
    <div className="placeholder">
      <h3>Not wired yet</h3>
      <p>This view needs the <code>{needs}</code> source, which isn't built yet —
         a placeholder beats fabricated data.</p>
    </div>
  );
}

// ---- action surface (todos) ----
// editable action list: an embedded quick-add bar + the lens, with each row
// opening the full editor; saves refresh the list.
export function EditableTodos({ lens, area }) {
  const [editing, setEditing] = useState(null);   // a todo object, or null
  const [reload, setReload] = useState(0);
  const r = useAsync(() => api.todos(lens, area), [lens, area, reload]);
  // the calendar lens also surfaces the events you're going to (read-only here;
  // decide them on the Events view)
  const ev = useAsync(() => (lens === "calendar" ? api.events() : Promise.resolve({ events: [] })), [lens]);
  const goingEvents = (ev.data?.events || []).filter((e) => e.status === "go" || e.status === "attended");
  const refresh = () => setReload((n) => n + 1);
  // assignee picker per task (docs/27) — a render-prop so the ActionRow in
  // primitives.jsx stays decoupled from the users API.
  const asg = useAssignment("todos");
  const renderAssignee = asg.ready
    ? (t) => <AssigneePicker entity="todos" id={t.todo_id}
               current={asg.map["todos:" + t.todo_id]} users={asg.users} onChanged={asg.refresh} />
    : null;

  // Done / Archive with an undo grace period: the row is hidden immediately and
  // the write is deferred ~5s, so "Undo" just cancels it (nothing to reverse).
  // A new action first commits the previous one. Backs the ✓/archive buttons
  // and the swipe gestures alike.
  const [hidden, setHidden] = useState([]);        // ids optimistically removed
  const [pendingLabel, setPendingLabel] = useState(null);
  const pendingRef = useRef(null);
  const clear = (id) => setHidden((h) => h.filter((x) => x !== id));
  function act(t, kind) {
    flush();                                       // commit any prior pending
    setHidden((h) => [...h, t.todo_id]);
    setPendingLabel(kind === "done" ? "Marked done" : "Archived");
    const commit = () => {
      pendingRef.current = null; setPendingLabel(null);
      const call = kind === "done" ? api.completeTodo(t.todo_id) : api.archiveTodo(t.todo_id);
      call.then(() => { clear(t.todo_id); refresh(); })
          .catch(() => { clear(t.todo_id); refresh(); });
    };
    pendingRef.current = { id: t.todo_id, commit, timer: setTimeout(commit, 5000) };
  }
  function undo() {
    const p = pendingRef.current; if (!p) return;
    clearTimeout(p.timer); pendingRef.current = null; setPendingLabel(null); clear(p.id);
  }
  function flush() {
    const p = pendingRef.current;
    if (p) { clearTimeout(p.timer); p.commit(); }
  }
  const markDone = (t) => act(t, "done");
  const markArchived = (t) => act(t, "archive");
  const visible = (list) => (list || []).filter((t) => !hidden.includes(t.todo_id));

  // drag-reorder persists in the pipeline lens (priority-ranked); not in Now
  // (urgency-sorted) or the calendar (date-grouped)
  const onReorder = lens === "pipeline"
    ? (ids) => api.reorderTodos(ids).then(refresh).catch(refresh)
    : null;
  // the week grid leads the calendar lens; in the pipeline lens (operations)
  // it appears only once there are todos with deadlines
  const datedTodos = visible(r.data?.todos).filter((t) => t.due_date);
  const showWeek = !r.loading && !r.err && lens !== "now" &&
    (lens === "calendar" || datedTodos.length > 0);
  return (
    <>
      {showWeek &&
        <WeekCalendar todos={lens === "calendar" ? visible(r.data.todos) : datedTodos}
                      events={goingEvents} onEdit={setEditing} />}
      <QuickAdd defaultArea={area || "operations"} onAdded={refresh} />
      {r.loading ? <Loading label="Loading actions…" /> : r.err ? <ErrorBox msg={r.err} />
        : lens === "calendar"
          ? <ActionCalendar todos={visible(r.data.todos)} onEdit={setEditing}
                            onDone={markDone} onArchive={markArchived} renderAssignee={renderAssignee} />
          : <ActionPipeline todos={visible(r.data.todos)} showArea={lens === "now"}
                            onEdit={setEditing} onDone={markDone} onArchive={markArchived}
                            onReorder={onReorder} renderAssignee={renderAssignee} />}
      {pendingLabel && (
        <div className="snackbar" role="status">
          <span>{pendingLabel}</span>
          <button className="snack-undo" onClick={undo}>Undo</button>
        </div>
      )}
      {editing && (
        <TodoEditor todo={editing} defaultArea={area || "operations"}
                    onClose={() => setEditing(null)}
                    onSaved={() => { setEditing(null); refresh(); }} />
      )}
    </>
  );
}
function NowAction() { return <EditableTodos lens="now" />; }
function AreaAction({ area, lens }) { return <EditableTodos lens={lens} area={area} />; }

// embedded quick-add: type an action and press Enter. Aito infers the type
// (area) and fills the relevant blanks ~half a second after you stop typing;
// only a couple of fields are shown — the full editor (row click) has the rest.
export function QuickAdd({ defaultArea, onAdded }) {
  const opts = useAsync(() => api.todoOptions(), []);
  const [title, setTitle] = useState("");
  const [area, setArea] = useState(defaultArea);
  const areaTouched = useRef(false);
  const [stakeholderId, setStakeholderId] = useState("");
  const [due, setDue] = useState(() => new Date().toISOString().slice(0, 10));
  const [slot, setSlot] = useState("10:30");
  const [infer, setInfer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // debounced auto-classify — fires once you pause typing, not on every key
  useEffect(() => {
    if (!title.trim()) { setInfer(null); return; }
    const h = setTimeout(async () => {
      try {
        const r = await api.classifyTodo(title, {});
        const a = r.suggest?.area?.top, act = r.suggest?.action_type?.top;
        setInfer({ area: a, action_type: act, stakeholders: r.stakeholders || [] });
        if (!areaTouched.current && a) setArea(a.value);
        if (r.stakeholders?.length) setStakeholderId((cur) => cur || r.stakeholders[0].id);
      } catch { /* best-effort only */ }
    }, 500);
    return () => clearTimeout(h);
  }, [title]);

  if (opts.loading) return null;
  if (opts.err) return <ErrorBox msg={opts.err} />;
  const o = opts.data;
  const isCal = o.calendar_areas.includes(area);

  async function add() {
    if (!title.trim() || busy) return;
    setBusy(true); setErr(null);
    try {
      await api.createTodo({
        area, title, action_type: infer?.action_type?.value || "",
        priority: 2, status: "ready", prep_status: isCal ? "ready" : "n_a",
        due_date: isCal ? due : "", window: "", slot: isCal ? slot : "",
        stakeholder_id: stakeholderId, linked_id: "", linked_type: "", detail: "",
      });
      setTitle(""); setInfer(null); setStakeholderId(""); setArea(defaultArea);
      areaTouched.current = false;
      onAdded();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }

  return (
    <div className="quickadd">
      <div className="qa-row">
        <input className="qa-title" value={title} autoFocus
               placeholder="Add an action… e.g. Call Bob at Acme"
               onChange={(e) => setTitle(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
        <select className="qa-field" value={area} title="type"
                onChange={(e) => { setArea(e.target.value); areaTouched.current = true; }}>
          {o.areas.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        {isCal && <input className="qa-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />}
        {isCal && <input className="qa-due" type="time" value={slot} title="time slot"
                         onChange={(e) => setSlot(e.target.value)} />}
        <select className="qa-field" value={stakeholderId} title="person"
                onChange={(e) => setStakeholderId(e.target.value)}>
          <option value="">person…</option>
          {o.contacts.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
        </select>
        <button className="qa-add" onClick={add} disabled={busy || !title.trim()}>Add</button>
      </div>
      {infer && (
        <div className="qa-infer">
          ✦ Aito: {infer.area && <><b>{infer.area.value}</b> ({Math.round(infer.area.p * 100)}%)</>}
          {infer.action_type && <> · {infer.action_type.value}</>}
          {infer.stakeholders?.length > 0 && <> · matched {infer.stakeholders[0].name}</>}
        </div>
      )}
      {err && <div className="error">{err}</div>}
    </div>
  );
}

const _EDIT_FIELDS = ["area", "title", "action_type", "priority", "status",
                      "prep_status", "due_date", "window", "slot", "stakeholder_id", "linked_id",
                      "role", "owner"];

export function TodoEditor({ todo, defaultArea, onClose, onSaved }) {
  const opts = useAsync(() => api.todoOptions(), []);
  const init = {
    area: todo?.area || defaultArea, title: todo?.title || "",
    action_type: todo?.action_type || "", priority: todo?.priority || 2,
    status: todo?.status || "ready", prep_status: todo?.prep_status || "n_a",
    due_date: todo?.due_date || "", window: todo?.window || "", slot: todo?.slot || "",
    stakeholder_id: todo?.stakeholder_id || "",
    linked_id: todo?.linked_type === "deal" ? (todo?.linked_id || "") : "",
    role: todo?.role || "", owner: todo?.owner || "",
    detail: todo?.detail || "",
  };
  const [f, setF] = useState(init);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [hints, setHints] = useState(null);   // Aito suggestions, shown for confirmation
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  // suggest the blank classifying fields from the title (Aito), then let the
  // operator confirm/override before saving — never auto-applied silently.
  async function suggest() {
    setBusy(true); setErr(null);
    try {
      const r = await api.classifyTodo(f.title, {});
      const s = r.suggest || {};
      setF((p) => ({
        ...p,
        area: s.area ? s.area.top.value : p.area,
        action_type: s.action_type ? s.action_type.top.value : p.action_type,
        stakeholder_id: (!p.stakeholder_id && r.stakeholders?.length)
          ? r.stakeholders[0].id : p.stakeholder_id,
      }));
      setHints({
        area: s.area?.top, action_type: s.action_type?.top,
        stakeholders: r.stakeholders || [],
      });
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  const hintBadge = (k) => hints?.[k] &&
    <span className="hint">Aito {Math.round(hints[k].p * 100)}%</span>;

  if (opts.loading) return <Modal onClose={onClose}><Loading label="Loading form…" /></Modal>;
  if (opts.err) return <Modal onClose={onClose}><ErrorBox msg={opts.err} /></Modal>;
  const o = opts.data;
  const isCal = o.calendar_areas.includes(f.area);
  // due/slot are allowed on calendar areas (required) and deadline areas
  // (operations — optional); forbidden elsewhere
  const dueAllowed = isCal || (o.deadline_areas || []).includes(f.area);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const norm = (k) => (k === "priority" ? Number(f[k])
        : (k === "due_date" || k === "window" || k === "slot") ? (dueAllowed ? f[k] : "") : f[k]);
      if (todo) {
        const changes = {};
        for (const k of _EDIT_FIELDS) {
          const v = norm(k);
          if (v !== (init[k] ?? "")) changes[k] = v;
        }
        if (f.detail !== (init.detail ?? "")) changes.detail = f.detail;
        if ("linked_id" in changes) changes.linked_type = changes.linked_id ? "deal" : "";
        await api.updateTodo(todo.todo_id, changes);
      } else {
        const fields = Object.fromEntries(_EDIT_FIELDS.map((k) => [k, norm(k)]));
        fields.detail = f.detail;
        fields.linked_type = fields.linked_id ? "deal" : "";
        await api.createTodo(fields);
      }
      onSaved();
    } catch (e) { setErr(e.message); setBusy(false); }
  }

  async function complete() {
    setBusy(true); setErr(null);
    try { await api.completeTodo(todo.todo_id); onSaved(); }
    catch (e) { setErr(e.message); setBusy(false); }
  }

  async function archive() {
    setBusy(true); setErr(null);
    try { await api.archiveTodo(todo.todo_id); onSaved(); }
    catch (e) { setErr(e.message); setBusy(false); }
  }

  return (
    <Modal onClose={onClose}>
      <h3>{todo ? "Edit action" : "New action"}</h3>
      <label className="fld">title
        <input value={f.title} onChange={set("title")} autoFocus placeholder="e.g. Call Globex / Mika" />
      </label>
      <div className="suggest-bar">
        <button className="suggest-btn" onClick={suggest} disabled={busy || !f.title.trim()}>
          ✦ Suggest fields from Aito
        </button>
        {hints && <span className="suggest-note">filled the blanks — confirm or change below</span>}
      </div>
      <div className="fld-row">
        <label className="fld">area {hintBadge("area")}
          <select value={f.area} onChange={set("area")}>
            {o.areas.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <label className="fld">action type {hintBadge("action_type")}
          <select value={f.action_type} onChange={set("action_type")}>
            <option value="">—</option>
            {o.action_types.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <label className="fld">priority
          <input type="number" min="1" max="5" value={f.priority} onChange={set("priority")} />
        </label>
      </div>
      <div className="fld-row">
        <label className="fld">status
          <select value={f.status} onChange={set("status")}>
            {o.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="fld">prep
          <select value={f.prep_status} onChange={set("prep_status")}>
            {o.prep_statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {dueAllowed && (
          <label className="fld">due{isCal ? "" : " (optional)"}
            <input type="date" value={f.due_date} onChange={set("due_date")} />
          </label>
        )}
      </div>
      {dueAllowed && (
        <div className="fld-row">
          <label className="fld">time slot
            <input type="time" value={f.slot} onChange={set("slot")} />
          </label>
          {isCal && (
            <label className="fld">window
              <input value={f.window} onChange={set("window")} placeholder="e.g. fri_1430" />
            </label>
          )}
        </div>
      )}
      <label className="fld">stakeholder
        {hints?.stakeholders?.length > 0 &&
          <span className="hint">matched: {hints.stakeholders.map((s) => s.name).join(", ")}</span>}
        <select value={f.stakeholder_id} onChange={set("stakeholder_id")}>
          <option value="">—</option>
          {o.contacts.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
        </select>
      </label>
      <label className="fld">deal
        <select value={f.linked_id} onChange={set("linked_id")}>
          <option value="">—</option>
          {o.deals.map((d) => <option key={d.id} value={d.id}>{d.company} ({d.stage})</option>)}
        </select>
      </label>
      <div className="fld-row">
        <label className="fld">agent lane
          <input list="lane-opts" value={f.role} onChange={set("role")}
                 placeholder="e.g. aito-core · operator" />
          <datalist id="lane-opts">
            {(o.lanes || []).map((l) => <option key={l} value={l} />)}
          </datalist>
        </label>
        <label className="fld">owner
          <input list="owner-opts" value={f.owner} onChange={set("owner")}
                 placeholder="agent instance, e.g. core-a" />
          <datalist id="owner-opts">
            {(o.owners || []).map((w) => <option key={w} value={w} />)}
          </datalist>
        </label>
      </div>
      <div className="suggest-note" style={{ margin: "-8px 0 14px" }}>
        Routes the task to an agent lane (a repo slug or <code>operator</code>); agents filter
        their queue on it — no need to name the agent in the title. Owner names one
        instance when a lane is run by several.
      </div>
      <label className="fld">detail
        <textarea value={f.detail} onChange={set("detail")} rows={6}
                  placeholder="notes, links, a longer description…" />
      </label>
      {err && <div className="error">Save error: {err}</div>}
      <div className="modal-actions">
        {todo && <button className="ghost" onClick={complete} disabled={busy}>Mark done</button>}
        {todo && <button className="ghost" onClick={archive} disabled={busy}
                         title="abandon this action — drops it without advancing anything">Archive</button>}
        <span className="spacer" />
        <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !f.title.trim()}>
          {todo ? "Save" : "Create"}
        </button>
      </div>
    </Modal>
  );
}

function Modal({ children, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}

// ---- Segment 360 (kpi-row + why + levers per KPI) ----
export function Segment360() {
  const dims = useAsync(() => api.dimensions(), []);
  const [slice, setSlice] = useState({});
  const set = (k, v) => setSlice((s) => ({ ...s, [k]: v }));
  if (dims.loading) return <Loading />;
  if (dims.err) return <ErrorBox msg={dims.err} />;
  return (
    <>
      <div className="controls">
        {dims.data.dimensions.map((d) => (
          <Select key={d} label={d} value={slice[d] || ""} allowAll
                  options={dims.data.values[d]} onChange={(v) => set(d, v)} />
        ))}
      </div>
      <Segment360Body slice={slice} />
    </>
  );
}

// "KPIs & the lever that moves each" — one card per KPI: rate + root causes
// (_relate) + recommended levers (_recommend) + the top lever's projected lift.
// Every number is Aito's; the ×badges are ratios of Aito's rates (formatting).
const BAND_HEX = { ok: "#0fa39b", mid: "#b07512", low: "#d4543a" };
const kpiBand = (rate) => (rate >= 0.5 ? "ok" : rate >= 0.2 ? "mid" : "low");

function Segment360Body({ slice }) {
  const r = useAsync(() => api.segment360(slice), [JSON.stringify(slice)]);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  return (
    <>
      <div className="block-head"><h2>KPIs &amp; the lever that moves each</h2>
        <span className="ptype">_predict · _relate · _recommend</span></div>
      <div className="k360grid">
        {r.data.kpis.map((k) => {
          const band = kpiBand(k.rate);
          const proj = k.lever?.options?.[0]?.p;
          const pp = proj != null ? Math.round((proj - k.rate) * 100) : null;
          return (
            <div className="k360" key={k.key}>
              <div className="k360h"><span className="k360t">{k.label}</span>
                <span className="k360s">good = {k.good_when_true}</span></div>
              <div className="k360big"><span className={"p " + band}>{pct(k.rate)}</span></div>
              <div className="kbar"><span style={{ width: Math.round(k.rate * 100) + "%", background: BAND_HEX[band] }} /></div>
              <div className="kl">Root causes <span className="rtag">_relate</span></div>
              {k.causes?.length ? k.causes.slice(0, 3).map((c, i) => {
                const ratio = c.rate_without ? c.rate_with / c.rate_without : null;
                return (
                  <div className="krow" key={i}>
                    <span className="kn"><b>{(c.field || "").replace("contact_id.", "")}</b> = {String(c.value)}</span>
                    {ratio != null && <span className={"mul " + (ratio >= 1 ? "risk" : "good")}>×{ratio.toFixed(2)}</span>}
                  </div>
                );
              }) : <div className="empty">no strong driver at this slice size</div>}
              {k.lever?.options?.length ? (<>
                <div className="kl">Lever: {k.lever.field} <span className="rtag">_recommend</span></div>
                {k.lever.options.slice(0, 3).map((o, i) => {
                  const up = k.rate ? o.p / k.rate : null;
                  return (
                    <div className="krow" key={i}>
                      <span className="kn">{k.lever.field} → {o.value}</span>
                      {up != null && <span className={"mul " + (up >= 1 ? "good" : "risk")}>×{up.toFixed(2)}</span>}
                    </div>
                  );
                })}
              </>) : null}
              {pp != null && pp > 0 && (
                <div className="kfoot">↳ pull the top lever → <b>{pct(proj)}</b> · {pp}pp better</div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

// ---- Funnel (chart + outlook/causes/lever) ----
export function FunnelView({ only }) {
  const cat = useAsync(() => api.funnelCatalog(), []);
  const [name, setName] = useState(only || "website");
  const [slice, setSlice] = useState({});
  if (cat.loading) return <Loading />;
  if (cat.err) return <ErrorBox msg={cat.err} />;
  const funnels = only ? cat.data.funnels.filter((f) => f.key === only) : cat.data.funnels;
  const spec = funnels.find((f) => f.key === name) || funnels[0];
  return (
    <>
      <div className="controls">
        {!only && (
          <Select label="funnel" value={spec.key} options={funnels.map((f) => f.key)}
                  onChange={(v) => { setName(v); setSlice({}); }} />
        )}
        {spec.dimensions.map((d) => (
          <Select key={d} label={d} value={slice[d] || ""} allowAll
                  options={spec.values[d]} onChange={(v) => setSlice((s) => ({ ...s, [d]: v }))} />
        ))}
      </div>
      <FunnelBody name={spec.key} slice={slice} />
    </>
  );
}

function FunnelBody({ name, slice }) {
  const r = useAsync(() => api.funnel(name, slice), [name, JSON.stringify(slice)]);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const d = r.data;
  return (
    <div className="cols">
      <Block title="The funnel" ptype="chart">
        <FunnelChart stages={d.stages} leak={d.leak} />
      </Block>
      <Block title="Aito read" ptype="predict">
        <div className="gauge">
          <div className={"p " + (d.outlook.p >= 0.5 ? "win" : d.outlook.p >= 0.2 ? "mid" : "low")}>
            {pct(d.outlook.p)}</div>
          <div className="lbl">calibrated P({d.deepest_label}) for this slice</div>
        </div>
        <div className="section-title">Why it leaks</div>
        <WhyList items={d.causes} />
        {d.lever && (<>
          <div className="section-title">Lever: {d.lever.field}</div>
          <div className="list">
            {d.lever.options.slice(0, 4).map((o, i) =>
              <BarRow key={i} name={o.value} p={o.p} num={pct(o.p)} dir={i === 0 ? "up" : ""} />)}
          </div>
        </>)}
      </Block>
    </div>
  );
}

// ---- Post scorer (optimizer primitive) ----
// the material × channel board: go/no-go status + KPIs, material/channel
// names joined from their catalogs.
function PostsBoard() {
  const posts = useAsync(() => api.table("posts"), []);
  const mats = useAsync(() => api.table("materials"), []);
  const chans = useAsync(() => api.table("channels"), []);
  if (posts.loading || mats.loading || chans.loading) return <Loading label="Loading posts…" />;
  // a missing table (instance not migrated to the marketing model yet) degrades
  // to a friendly empty, not a broken view
  if (posts.err || mats.err || chans.err)
    return <div className="empty">No posts yet — add materials, channels and posts
      (or run <code>./do migrate</code> if this instance predates the marketing model).</div>;
  const mt = Object.fromEntries(mats.data.rows.map((m) => [m.material_id, m.title]));
  const ch = Object.fromEntries(chans.data.rows.map((c) => [c.channel_id, c.name]));
  const rows = posts.data.rows;
  const by = (s) => rows.filter((r) => r.status === s).length;
  return (
    <>
      <KpiRow items={[
        { label: "posted", value: by("posted") },
        { label: "planned / go", value: by("planned") + by("go") },
        { label: "no-go", value: by("no_go") },
      ]} />
      <div className="actions">
        {rows.slice(0, 50).map((p) => (
          <div className="arow" key={p.post_id}>
            <div className="amid">
              <div className="att">{mt[p.material_id] || p.material_id}
                <span className="co"> · {ch[p.channel_id] || p.channel_id}</span></div>
              <div className="amm">
                {p.platform} · {p.tone}
                {p.outcome ? <> · <b>{p.outcome}</b></> : null}
                {p.reach_or_views != null ? ` · ${p.reach_or_views.toLocaleString()} reach/views` : ""}
              </div>
            </div>
            <div className={"st " + p.status}>{p.status.replace("_", "-")}</div>
          </div>
        ))}
      </div>
    </>
  );
}

export function Scorer() {
  const opts = useAsync(() => api.scoreOptions(), []);
  const [platform, setPlatform] = useState("linkedin");
  const [feat, setFeat] = useState({
    tone: "narrate", ai_made: "manual", format: "link",
    link_placement: "comment", lane: "warm", topic: "agent_inference",
    length_bucket: "medium", weekday: "wed",
  });
  if (opts.loading) return <Loading />;
  if (opts.err) return <ErrorBox msg={opts.err} />;
  const set = (k, v) => setFeat((f) => ({ ...f, [k]: v }));
  return (
    <div className="cols">
      <Block title="Draft" ptype="optimizer">
        <div className="controls" style={{ flexDirection: "column", alignItems: "stretch" }}>
          <Select label="platform" value={platform} options={opts.data.options.platform} onChange={setPlatform} />
          {opts.data.features.map((f) => (
            <Select key={f} label={f} value={feat[f] || ""} allowAll
                    options={opts.data.options[f]} onChange={(v) => set(f, v)} />
          ))}
        </div>
      </Block>
      <ScorerRead platform={platform} feat={feat} />
    </div>
  );
}

function ScorerRead({ platform, feat }) {
  const r = useAsync(() => api.score(platform, feat), [platform, JSON.stringify(feat)]);
  if (r.loading) return <Block title="Aito read" ptype="predict"><Loading /></Block>;
  if (r.err) return <Block title="Aito read" ptype="predict"><ErrorBox msg={r.err} /></Block>;
  const d = r.data;
  return (
    <Block title={"Aito read — " + d.platform} ptype="predict">
      <div className="gauge">
        <div className={"p " + (d.p_win >= 0.5 ? "win" : d.p_win >= 0.2 ? "mid" : "low")}>{pct(d.p_win)}</div>
        <div className="lbl">predicted P(win) for this draft</div>
      </div>
      <div className="base">platform base {pct(d.base_p_win)} — this draft is {d.p_win >= d.base_p_win ? "above" : "below"} it</div>
      <div className="section-title">What moved the prediction</div>
      <WhyList items={d.why} />
      <div className="section-title">Levers</div>
      <Levers levers={d.levers} />
    </Block>
  );
}

// ---- Deals (pipeline + close-likelihood) ----
const eur = (n) => "€" + (n || 0).toLocaleString();

function Deals() {
  const r = useAsync(() => api.deals(), []);
  const asg = useAssignment("deals");
  const deals = usePwin(r.data?.deals);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const { kpis } = r.data;
  return (
    <>
      <KpiRow items={[
        { label: "weighted pipeline", value: eur(kpis.weighted_pipeline) },
        { label: "open value", value: eur(kpis.open_value), sub: `${kpis.open_deals} deals` },
        { label: "stalled", value: kpis.stalled, sub: "no touch > 14d" },
      ]} />
      <div className="section-title">Open deals — weighted value, Aito close-likelihood</div>
      <div className="actions">
        {deals.map((d) => {
          const pw = d.p_win == null ? null : Math.round(d.p_win * 100);
          const band = pw == null ? "" : pw >= 50 ? "lo" : pw >= 25 ? "mid" : "hi"; // low win = high risk
          const why = d.why?.[0]?.label;
          return (
            <div className="deal" key={d.deal_id}>
              <div className="dval">{eur(d.weighted_value)}</div>
              <div className="dmid">
                <div className="att">{d.company} <span className="co">· {d.stage} · {eur(d.value_eur)}</span></div>
                <div className="amm">
                  <span>own {d.probability}%</span>
                  {pw != null && <span> · Aito {pw}%{why ? " (" + why + ")" : ""}</span>}
                  {d.stalled && <span className="area"> · stalled {d.days_since_touch}d</span>}
                  {d.blocker !== "none" && <span> · {d.blocker.replace(/_/g, " ")}</span>}
                </div>
              </div>
              {pw != null && <span className={"slip " + band} title={why ? "driver: " + why : ""}>win {pw}%</span>}
              {asg.ready && <AssigneePicker entity="deals" id={d.deal_id}
                current={asg.map["deals:" + d.deal_id]} users={asg.users} onChanged={asg.refresh} />}
            </div>
          );
        })}
      </div>
    </>
  );
}

// ---- Companies (contacts rolled up by company, joined to deals) ----
function Companies() {
  const r = useAsync(() => api.companies(), []);
  if (r.loading) return <Loading label="Rolling up companies…" />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const { companies, count } = r.data;
  if (!count) return <div className="empty">no companies yet — contacts and deals roll up here</div>;
  return (
    <>
      <div className="section-title">{count} companies — contacts + pipeline, most live money first</div>
      <div className="co-list">
        {companies.map((c) => (
          <div className="co-row co-click" key={c.company} role="button" tabIndex={0}
               title="open the company"
               onClick={() => { window.location.hash = "/company/" + c.company_id; }}>
            <div className="co-main">
              <div className="co-name">{c.company}</div>
              <div className="co-sub">
                {c.contacts} contact{c.contacts === 1 ? "" : "s"}
                {c.segment && <> · {c.segment}</>}
                <> · {c.stage}</>
                {c.won && <span className="co-won"> · won</span>}
              </div>
            </div>
            <div className="co-deals">
              {c.open_deals > 0
                ? <><span className="co-eur">{eur(c.pipeline_eur)}</span>
                    <span className="co-dsub">{c.open_deals} open{c.deals > c.open_deals ? ` / ${c.deals}` : ""}</span></>
                : c.deals > 0
                  ? <span className="co-dsub">{c.deals} closed</span>
                  : <span className="co-dsub">—</span>}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ---- Company detail: one node, its people + deals + notes (the graph drill-in)
export function CompanyDetail({ companyId }) {
  const r = useAsync(() => api.companyDetail(companyId), [companyId]);
  if (!companyId) return <div className="empty">no company selected</div>;
  if (r.loading) return <Loading label="Loading company…" />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const d = r.data;
  return (
    <div className="company-detail">
      <button className="doc-back" onClick={() => { window.location.hash = "/sales"; }}>← Companies</button>
      <h2 className="cd-name">{d.name}</h2>
      <div className="cd-cols">
        <section className="cd-block">
          <h3>Notes ({d.documents.length})</h3>
          {d.documents.length ? d.documents.map((n) => (
            <button key={n.doc_id} className="cd-note"
                    onClick={() => { window.location.hash = "/documents/" + n.doc_id; }}>
              <span className="cd-note-t">{n.title}</span>
              {n.noted_on && <span className="cd-note-d">{n.noted_on}</span>}
              {n.topics && <span className="cd-note-tags">
                {n.topics.split(";").filter(Boolean).slice(0, 3).join(" · ")}</span>}
            </button>
          )) : <div className="muted">no notes yet — add one with ＋ Note</div>}
        </section>
        <section className="cd-block">
          <h3>People ({d.contacts.length})</h3>
          {d.contacts.length ? d.contacts.map((c) => (
            <div key={c.id} className="cd-row"><b>{c.name}</b>
              {c.role ? ` · ${c.role}` : ""}{c.tier ? ` · ${c.tier}` : ""}</div>
          )) : <div className="muted">none</div>}
          <h3 className="cd-h2">Deals ({d.deals.length})</h3>
          {d.deals.length ? d.deals.map((dl) => (
            <div key={dl.deal_id} className="cd-row">{dl.stage}
              {dl.value_eur != null ? ` · ${eur(dl.value_eur)}` : ""}
              {dl.probability != null ? ` · ${dl.probability}%` : ""}</div>
          )) : <div className="muted">none</div>}
        </section>
      </div>
    </div>
  );
}

// ---- Decisions (the dogfood scorecard) ----
function Decisions() {
  const r = useAsync(() => api.decisions(), []);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const d = r.data;
  if (!d.total) return <div className="empty">no decisions logged yet — the loop fills as the agent recommends and you accept/override</div>;
  return (
    <>
      <KpiRow items={[
        { label: "decisions logged", value: d.total },
        { label: "acceptance rate", value: pct(d.acceptance) },
        { label: "confidence trustworthy", value: d.trustworthy ? "yes ↑" : "not yet" },
      ]} />
      <Block title="Acceptance by decision type" ptype="kpi-row">
        <div className="list">
          {d.by_type.map((t) => (
            <BarRow key={t.type} name={`${t.type} (${t.n})`} p={t.rate}
                    num={pct(t.rate)} dir={t.rate >= d.acceptance ? "up" : "down"} />
          ))}
        </div>
      </Block>
      <Block title="Is the agent's confidence trustworthy?" ptype="predict"
             note="P(accepted) should climb low → high">
        <div className="list">
          {d.calibration.map((c) => (
            <BarRow key={c.bucket} name={`${c.bucket} confidence (${c.n})`}
                    p={c.aito_p} num={c.aito_p == null ? "–" : pct(c.aito_p)}
                    dir="up" />
          ))}
        </div>
      </Block>
    </>
  );
}

// ---- Experiments (the Build-Measure-Learn board) ----
function Experiments() {
  const r = useAsync(() => api.experiments(), []);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const d = r.data;
  if (!d.total) return <div className="empty">no experiments yet — start one with a hypothesis and a target metric</div>;
  return (
    <>
      <KpiRow items={[
        { label: "experiments", value: d.total },
        { label: "validated-learning rate", value: pct(d.validated_learning_rate), sub: `${d.status_mix.validated}/${d.decided} decided` },
        { label: "running now", value: d.running.length },
        { label: "favour small bets", value: d.favour_small ? "yes ↑" : "unclear" },
      ]} />
      <Block title="Which bets pay off?" ptype="predict"
             note="P(validated) by effort — small/cheap should win">
        <div className="list">
          {d.by_effort.map((b) => (
            <BarRow key={b.effort} name={`${b.effort} effort (${b.decided} decided)`}
                    p={b.aito_p} num={b.aito_p == null ? "–" : pct(b.aito_p)}
                    dir={b.effort === "small" ? "up" : "down"} />
          ))}
        </div>
      </Block>
      <Block title={`Running bets (${d.running.length})`} ptype="action-pipeline">
        {d.running.length === 0
          ? <div className="empty">nothing in flight</div>
          : <div className="actions">
              {d.running.map((e) => (
                <div className="arow" key={e.experiment_id}>
                  <div className="amid">
                    <div className="att">{e.hypothesis}</div>
                    <div className="amm">
                      <span className="area">{e.area}</span>
                      <span>{e.type} · {e.effort} · started {e.started}</span>
                    </div>
                  </div>
                  <div className="st">{e.metric}: {e.baseline} → {e.target}</div>
                </div>
              ))}
            </div>}
      </Block>
    </>
  );
}

// ---- My work + team (users & assignees, docs/27) ----
// A dropdown to (re)assign a work item to a user. Ownership lives in a join
// table (docs/27), so this just POSTs the assignment; the CRM row is untouched.
// Shared assignment state for a list view: the active users and the current
// owner per item ("entity:id" -> user_id), refetched after any (re)assignment.
function useAssignment(entity) {
  const [reload, setReload] = useState(0);
  const us = useAsync(() => api.users(), []);
  const as = useAsync(() => api.assignments(entity), [reload]);
  return {
    users: (us.data?.users || []).filter((u) => u.active),
    map: as.data?.map || {},
    ready: !us.loading && !as.loading && !us.err && !as.err,
    refresh: () => setReload((n) => n + 1),
  };
}

function AssigneePicker({ entity, id, current, users, onChanged }) {
  const [busy, setBusy] = useState(false);
  const set = async (e) => {
    const uid = e.target.value || null;
    setBusy(true);
    try { await api.assign(entity, id, uid); onChanged && onChanged(uid); }
    finally { setBusy(false); }
  };
  return (
    <select className="assignee-select" value={current || ""} onChange={set} disabled={busy}
            onClick={(e) => e.stopPropagation()} title="assignee">
      <option value="">— unassigned</option>
      {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
    </select>
  );
}

export function MyWork() {
  const [reload, setReload] = useState(0);
  const refresh = () => setReload((n) => n + 1);
  const mw = useAsync(() => api.myWork(), [reload]);
  const us = useAsync(() => api.users(), []);
  if (mw.loading || us.loading) return <Loading label="Loading your work…" />;
  if (mw.err) return <ErrorBox msg={mw.err} />;
  if (us.err) return <ErrorBox msg={us.err} />;
  const users = us.data.users.filter((u) => u.active);
  const me = mw.data.user_id;
  const pick = (entity, id) => (
    <AssigneePicker entity={entity} id={id} current={me} users={users} onChanged={refresh} />
  );
  return (
    <>
      <KpiRow items={[
        { label: "assigned to me", value: mw.data.count },
        { label: "leads", value: mw.data.contacts.length },
        { label: "deals", value: mw.data.deals.length },
        { label: "tasks", value: mw.data.todos.length },
      ]} />
      {mw.data.count === 0 && <div className="empty">nothing assigned to you yet — the operator
        or the agent can assign leads, deals, and tasks to you.</div>}

      {mw.data.todos.length > 0 && <>
        <div className="section-title">My tasks</div>
        <div className="actions">
          {mw.data.todos.map((t) => (
            <div className="arow" key={t.todo_id}>
              <div className="amid"><div className="att">{t.title}</div>
                <div className="amm"><span className="area">{t.area}</span>
                  <span className="slot">{t.status}</span>
                  {t.due_date && <span> · due {t.due_date}</span>}</div></div>
              {pick("todos", t.todo_id)}
            </div>
          ))}
        </div>
      </>}

      {mw.data.deals.length > 0 && <>
        <div className="section-title">My deals</div>
        <div className="actions">
          {mw.data.deals.map((d) => (
            <div className="arow" key={d.deal_id}>
              <div className="amid"><div className="att">{d.company}</div>
                <div className="amm"><span className="area">{d.stage}</span>
                  <span className="slot">{pct(d.probability / 100)}</span>
                  {d.value_eur ? <span> · €{d.value_eur.toLocaleString()}</span> : null}</div></div>
              {pick("deals", d.deal_id)}
            </div>
          ))}
        </div>
      </>}

      {mw.data.contacts.length > 0 && <>
        <div className="section-title">My leads</div>
        <div className="actions">
          {mw.data.contacts.map((c) => (
            <div className="arow" key={c.contact_id}>
              <div className="amid"><div className="att">{c.name}</div>
                <div className="amm"><span className="area">{c.company}</span>
                  <span className="slot">{c.segment} · {c.tier}</span></div></div>
              {pick("contacts", c.contact_id)}
            </div>
          ))}
        </div>
      </>}

      <div className="asst-hint">Manage the team in <b>Admin</b> (operator only).</div>
    </>
  );
}

// ---- Admin: user management (operator-only, docs/27) ----
export function UsersAdmin() {
  const [reload, setReload] = useState(0);
  const refresh = () => setReload((n) => n + 1);
  const me = useAsync(() => api.me(), []);
  const us = useAsync(() => api.users(), [reload]);
  if (me.loading || us.loading) return <Loading label="Loading admin…" />;
  if (us.err) return <ErrorBox msg={us.err} />;
  if (me.data?.role !== "operator")
    return <div className="empty">Admin is operator-only. You're signed in as
      {" " + (me.data?.role || "guest")}.</div>;
  return (
    <>
      <div className="section-title">Users</div>
      <div className="actions">
        {us.data.users.map((u) => <UserRow key={u.user_id} u={u} onChanged={refresh} />)}
      </div>
      <AddUser onChanged={refresh} />
      <div className="asst-hint" style={{ marginTop: 18 }}>A user's <b>email</b> must match
        the Microsoft account they sign in with — that's how the app recognizes them.</div>
      <ApiTokens />
    </>
  );
}

// API tokens for the remote MCP (docs/28). The secret is shown once on creation
// and never again — only its hash is stored.
function ApiTokens() {
  const [reload, setReload] = useState(0);
  const refresh = () => setReload((n) => n + 1);
  const t = useAsync(() => api.tokens(), [reload]);
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [fresh, setFresh] = useState(null);   // {label, token} shown once
  const create = async () => {
    setBusy(true); setErr(null);
    try { const r = await api.createToken(label); setFresh(r); setLabel(""); setAdding(false); refresh(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const revoke = async (id) => { await api.revokeToken(id).catch(() => {}); refresh(); };
  const rows = t.data?.tokens || [];
  return (
    <div className="team" style={{ marginTop: 26 }}>
      <div className="section-title">Remote MCP tokens</div>
      <div className="asst-hint">Bearer tokens for connecting cloud Claude (claude.ai / Claude Code)
        to <code>/mcp</code>. Create one per connector; revoke anytime. The secret is shown once.</div>
      <div className="actions">
        {rows.map((tk) => (
          <div className={"arow" + (tk.active ? "" : " done")} key={tk.token_id}>
            <div className="amid">
              <div className="att">{tk.label}{!tk.active && <span className="atype">revoked</span>}</div>
              <div className="amm"><span className="slot">{tk.prefix}…</span>
                <span> · created {tk.created}</span></div>
            </div>
            {tk.active && <button className="ghost" onClick={() => revoke(tk.token_id)}>Revoke</button>}
          </div>
        ))}
        {!rows.length && <div className="empty">no tokens yet</div>}
      </div>
      {adding ? (
        <div className="fld-row team-add">
          <label className="fld">label<input value={label} onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. the operator's claude.ai connector" autoFocus /></label>
          <button className="primary" disabled={busy || !label.trim()} onClick={create}>Create</button>
          <button className="ghost" disabled={busy} onClick={() => setAdding(false)}>Cancel</button>
        </div>
      ) : <button className="new-todo" onClick={() => setAdding(true)}>+ New token</button>}
      {err && <div className="error">{err}</div>}
      {fresh && (
        <Modal onClose={() => setFresh(null)}>
          <h3>Token created — copy it now</h3>
          <p className="asst-hint">This is the only time <b>{fresh.label}</b> will be shown. Store it
            in your Claude connector as <code>Authorization: Bearer &lt;token&gt;</code>. We keep only
            a hash — if you lose it, revoke and make a new one.</p>
          <textarea className="prep-prompt" readOnly rows={2} value={fresh.token}
                    onFocus={(e) => e.target.select()} />
          <div className="modal-actions">
            <span className="spacer" />
            <button className="primary" onClick={() => setFresh(null)}>Done</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function UserRow({ u, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const patch = async (changes) => {
    setBusy(true); setErr(null);
    try { await api.updateUser(u.user_id, changes); onChanged(); }
    catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <div className={"arow" + (u.active ? "" : " done")}>
      <div className="amid">
        <div className="att">{u.name}{!u.active && <span className="atype">inactive</span>}</div>
        <div className="amm"><span className="slot">{u.email}</span></div>
      </div>
      <select className="assignee-select" value={u.role} disabled={busy}
              onChange={(e) => patch({ role: e.target.value })} title="role">
        <option value="operator">operator</option><option value="sdr">sdr</option>
      </select>
      <button className="ghost" disabled={busy} onClick={() => patch({ active: !u.active })}>
        {u.active ? "Deactivate" : "Reactivate"}</button>
      {err && <span className="error">{err}</span>}
    </div>
  );
}

function AddUser({ onChanged }) {
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ name: "", email: "", role: "sdr" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const save = async () => {
    setBusy(true); setErr(null);
    try { await api.createUser(f); setAdding(false); setF({ name: "", email: "", role: "sdr" }); onChanged(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  if (!adding) return <button className="new-todo" onClick={() => setAdding(true)}>+ Add user</button>;
  return (
    <>
      <div className="fld-row team-add">
        <label className="fld">name<input value={f.name} onChange={set("name")} /></label>
        <label className="fld">email<input value={f.email} onChange={set("email")} placeholder="their MS-account email" /></label>
        <label className="fld">role<select value={f.role} onChange={set("role")}>
          <option value="sdr">sdr</option><option value="operator">operator</option></select></label>
        <button className="primary" disabled={busy || !f.name.trim() || !f.email.trim()} onClick={save}>Add</button>
        <button className="ghost" disabled={busy} onClick={() => setAdding(false)}>Cancel</button>
      </div>
      {err && <div className="error">{err}</div>}
    </>
  );
}

// ---- Routines (recurring agentic tasks) ----
const _CAD = (r) => r.cadence === "weekly" ? `weekly · ${r.weekday}`
  : r.cadence === "monthly" ? `monthly · day ${r.day_of_month}` : "daily";

export function Routines() {
  const [reload, setReload] = useState(0);
  const r = useAsync(() => api.routines(), [reload]);
  const [editing, setEditing] = useState(null);   // routine | "new" | null
  const [pack, setPack] = useState(null);          // prepared run pack
  const [result, setResult] = useState(null);      // finished run (narration)
  const [running, setRunning] = useState(null);    // routine_id being run now
  const [busy, setBusy] = useState(false);
  const refresh = () => setReload((n) => n + 1);
  if (r.loading) return <Loading label="Loading routines…" />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const rows = r.data.routines;
  const tick = async (id) => { setBusy(true); try { await api.tickRoutine(id); } finally { setBusy(false); refresh(); } };
  const prepare = async (rt) => {
    setBusy(true);
    try { setPack({ routine: rt, ...(await api.prepareRoutine(rt.routine_id)) }); }
    catch (e) { setPack({ routine: rt, error: e.message }); } finally { setBusy(false); }
  };
  const run = async (rt) => {
    setRunning(rt.routine_id);
    try { setResult({ routine: rt, ...(await api.runRoutine(rt.routine_id)) }); }
    catch (e) { setResult({ routine: rt, error: e.message }); }
    finally { setRunning(null); refresh(); }
  };
  return (
    <>
      <KpiRow items={[
        { label: "routines", value: rows.length },
        { label: "due now", value: rows.filter((x) => x.due).length },
        { label: "overdue", value: rows.filter((x) => x.overdue).length },
      ]} />
      <div className="actions-bar"><button className="new-todo" onClick={() => setEditing("new")}>+ New routine</button></div>
      <div className="actions">
        {rows.map((rt) => (
          <div className={"arow editable" + (rt.overdue ? " p1" : "")} key={rt.routine_id}
               onClick={() => setEditing(rt)}>
            <button className="done-box" title="mark done for this period" disabled={busy}
                    onClick={(e) => { e.stopPropagation(); tick(rt.routine_id); }}>✓</button>
            <div className="amid">
              <div className="att">{rt.title}
                {rt.prep !== "none" && <span className="atype">{rt.prep}</span>}
                <button className="edit-pen" title="edit" onClick={(e) => { e.stopPropagation(); setEditing(rt); }}>✎</button></div>
              <div className="amm">
                <span className="area">{rt.area}</span>
                <span className="slot">{_CAD(rt)}</span>
                {rt.last_done && <span> · last {rt.last_done}</span>}
                {rt.notes && <span> · {rt.notes}</span>}
              </div>
            </div>
            {rt.prep !== "none" &&
              <button className="prep-btn" disabled={busy || running}
                      onClick={(e) => { e.stopPropagation(); prepare(rt); }}>Prepare ✦</button>}
            <button className="run-btn" disabled={busy || running}
                    title="run now through the assistant loop → document"
                    onClick={(e) => { e.stopPropagation(); run(rt); }}>
              {running === rt.routine_id ? "Running…" : "Run ▶"}</button>
            <div className={"st " + (rt.overdue ? "blocked" : rt.due ? "ready" : "done")}>
              {rt.overdue ? `overdue ${rt.days_overdue}d` : rt.due ? "due" : "done"}</div>
          </div>
        ))}
      </div>
      {editing && <RoutineEditor routine={editing === "new" ? null : editing}
                                 onClose={() => setEditing(null)}
                                 onSaved={() => { setEditing(null); refresh(); }} />}
      {pack && <PreparePanel pack={pack} onClose={() => setPack(null)} />}
      {result && <RunResultPanel result={result} onClose={() => setResult(null)} />}
    </>
  );
}

function PreparePanel({ pack, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard?.writeText(pack.prompt || ""); setCopied(true); };
  return (
    <Modal onClose={onClose}>
      <h3>Prepare — {pack.routine.title}</h3>
      {pack.error ? <ErrorBox msg={pack.error} /> : <>
        <p className="asst-hint">Run this in Claude (Desktop, with the MCP tools). The app
          prepared it from Aito; Claude executes it.</p>
        {pack.candidates?.length > 0 && (
          <div className="prep-cands">
            {pack.candidates.map((c) => (
              <div key={c.contact_id} className="prep-cand">
                <span>{c.company}</span><span className="hint">P {pct(c["$p"])}</span>
              </div>
            ))}
          </div>
        )}
        <textarea className="prep-prompt" readOnly value={pack.prompt} rows={8} />
        <div className="modal-actions">
          <span className="spacer" />
          <button className="ghost" onClick={onClose}>Close</button>
          <button className="primary" onClick={copy}>{copied ? "Copied ✓" : "Copy prompt"}</button>
        </div>
      </>}
    </Modal>
  );
}

function RunResultPanel({ result, onClose }) {
  const n = (x, one, many) => `${x} ${x === 1 ? one : many}`;
  return (
    <Modal onClose={onClose}>
      <h3>Ran — {result.routine.title}</h3>
      {result.error ? <ErrorBox msg={result.error} /> : <>
        <p className="asst-hint">Ran through the assistant loop
          ({n(result.tool_calls, "tool call", "tool calls")}, {n(result.rounds, "round", "rounds")})
          and saved the result as a dated document. Read-only — it narrated, it didn't act.</p>
        <div className="run-reply">{result.reply}</div>
        <div className="modal-actions">
          <span className="spacer" />
          <button className="primary" onClick={onClose}>Close</button>
        </div>
      </>}
    </Modal>
  );
}

function RoutineEditor({ routine, onClose, onSaved }) {
  const init = {
    title: routine?.title || "", area: routine?.area || "operations",
    cadence: routine?.cadence || "weekly", weekday: routine?.weekday || "mon",
    day_of_month: routine?.day_of_month || 1, prep: routine?.prep || "none",
    notes: routine?.notes || "",
  };
  const [f, setF] = useState(init);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  async function save() {
    setBusy(true); setErr(null);
    try {
      const fields = {
        title: f.title, area: f.area, cadence: f.cadence, prep: f.prep, notes: f.notes,
        weekday: f.cadence === "weekly" ? f.weekday : "",
        day_of_month: f.cadence === "monthly" ? Number(f.day_of_month) : null,
      };
      if (routine) await api.updateRoutine(routine.routine_id, fields);
      else await api.createRoutine(fields);
      onSaved();
    } catch (e) { setErr(e.message); setBusy(false); }
  }
  return (
    <Modal onClose={onClose}>
      <h3>{routine ? "Edit routine" : "New routine"}</h3>
      <label className="fld">title<input value={f.title} onChange={set("title")} autoFocus
        placeholder="e.g. Monday outreach prep" /></label>
      <div className="fld-row">
        <label className="fld">area<select value={f.area} onChange={set("area")}>
          {["sales", "marketing", "operations", "rnd", "experiments"].map((a) => <option key={a}>{a}</option>)}
        </select></label>
        <label className="fld">cadence<select value={f.cadence} onChange={set("cadence")}>
          {["daily", "weekly", "monthly"].map((c) => <option key={c}>{c}</option>)}
        </select></label>
        {f.cadence === "weekly" &&
          <label className="fld">weekday<select value={f.weekday} onChange={set("weekday")}>
            {["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => <option key={d}>{d}</option>)}
          </select></label>}
        {f.cadence === "monthly" &&
          <label className="fld">day<input type="number" min="1" max="28" value={f.day_of_month}
            onChange={set("day_of_month")} /></label>}
      </div>
      <label className="fld">prep (agentic recipe)<select value={f.prep} onChange={set("prep")}>
        <option value="none">none — a plain reminder</option>
        <option value="prospects">prospects — Aito candidates + a Claude prompt</option>
        <option value="brief">brief — the week-prep prompt</option>
      </select></label>
      <label className="fld">notes<textarea value={f.notes} onChange={set("notes")} rows={2} /></label>
      {err && <div className="error">Save error: {err}</div>}
      <div className="modal-actions">
        <span className="spacer" />
        <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !f.title.trim()}>
          {routine ? "Save" : "Create"}</button>
      </div>
    </Modal>
  );
}

// ---- Events to attend (the go/no-go board) ----
function Events() {
  const [reload, setReload] = useState(0);
  const r = useAsync(() => api.events(), [reload]);
  const [busy, setBusy] = useState(false);
  if (r.loading) return <Loading label="Loading events…" />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const events = r.data.events;
  const decide = async (id, body) => {
    setBusy(true);
    try { await api.decideEvent(id, body); } finally { setBusy(false); setReload((n) => n + 1); }
  };
  const by = (s) => events.filter((e) => e.status === s).length;
  const upcoming = [...events].sort((a, b) => (a.starts || "").localeCompare(b.starts || ""));
  return (
    <>
      <KpiRow items={[
        { label: "candidates", value: by("candidate") },
        { label: "going", value: by("go") },
        { label: "attended", value: by("attended") },
      ]} />
      <WeekCalendar events={events.filter((e) => e.status === "go" || e.status === "attended")} />
      <Block title="Events — go / no-go" ptype="action-pipeline">
        <div className="actions">
          {upcoming.map((e) => (
            <div className={"arow ev-" + e.status} key={e.event_id}>
              <div className="amid">
                <div className="att">{e.name}
                  <span className="co"> · {e.type}{e.location ? " · " + e.location : ""}
                    {e.cost_eur ? ` · €${e.cost_eur.toLocaleString()}` : ""}</span></div>
                <div className="amm">
                  <span className="slot">{e.starts}</span>
                  {e.outcome && <span> · outcome: <b>{e.outcome}</b></span>}
                  {e.notes && <span> · {e.notes}</span>}
                </div>
              </div>
              <div className="ev-actions">
                {e.status === "candidate" && <>
                  <button className="go" disabled={busy} onClick={() => decide(e.event_id, { status: "go" })}>Go</button>
                  <button className="nogo" disabled={busy} onClick={() => decide(e.event_id, { status: "no_go" })}>No-go</button>
                </>}
                {e.status === "go" && <>
                  {["worthwhile", "neutral", "waste"].map((o) => (
                    <button key={o} className="att" disabled={busy} title={"attended — " + o}
                            onClick={() => decide(e.event_id, { status: "attended", outcome: o })}>
                      {o === "worthwhile" ? "✓ went" : o === "neutral" ? "~ ok" : "✗ meh"}</button>
                  ))}
                  <button className="nogo" disabled={busy} onClick={() => decide(e.event_id, { status: "no_go" })}>drop</button>
                </>}
                {e.status === "no_go" &&
                  <button disabled={busy} onClick={() => decide(e.event_id, { status: "candidate" })}>reconsider</button>}
                <span className={"st " + e.status}>{e.status.replace("_", "-")}</span>
              </div>
            </div>
          ))}
        </div>
      </Block>
    </>
  );
}

// ---- Data sheets (raw rows of any table) ----
function DataView() {
  const list = useAsync(() => api.tables(), []);
  const [name, setName] = useState(null);
  if (list.loading) return <Loading />;
  if (list.err) return <ErrorBox msg={list.err} />;
  const tables = list.data.tables;
  if (!tables.length) return <div className="empty">no tables loaded</div>;
  const active = name || tables[0].name;
  return (
    <>
      <div className="controls">
        <Select label="table" value={active} options={tables.map((t) => t.name)} onChange={setName} />
        <div className="field" style={{ alignSelf: "center" }}>
          <span className="empty" style={{ fontStyle: "normal" }}>
            {tables.find((t) => t.name === active)?.count.toLocaleString()} rows
          </span>
        </div>
      </div>
      <SheetBody name={active} />
    </>
  );
}

// A view's own data tab: the raw rows behind that view, scoped to its
// slice(s). specs = [{table, where?, label?}]; a picker appears for >1 sheet.
export function ScopedData({ specs }) {
  const [i, setI] = useState(0);
  const labelOf = (s) => s.label || s.table;
  const spec = specs[Math.min(i, specs.length - 1)];
  return (
    <>
      {specs.length > 1 && (
        <div className="controls">
          <Select label="sheet" value={labelOf(spec)} options={specs.map(labelOf)}
                  onChange={(v) => setI(specs.findIndex((s) => labelOf(s) === v))} />
        </div>
      )}
      <SheetBody name={spec.table} where={spec.where} label={spec.label} />
    </>
  );
}

function SheetBody({ name, where, label }) {
  const r = useAsync(() => api.table(name, where), [name, JSON.stringify(where)]);
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  const { columns, rows, total, shown, truncated } = r.data;
  return (
    <Block title={`${label || name} — ${total.toLocaleString()} rows`} ptype="document-tree"
           note={truncated ? `showing first ${shown}` : ""}>
      <div className="sheetwrap">
        <table className="sheet">
          <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((c) => {
                  const v = row[c];
                  return <td key={c} className={typeof v === "number" ? "num" : ""}>
                    {v === undefined || v === null ? "" : String(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

function Chip({ on, onClick, children }) {
  return <button className={"chip" + (on ? " on" : "")} onClick={onClick}>{children}</button>;
}

// ---- Documents (the knowledge store, docs/25) ----
// The operator's own writing, kept in the tool: tagged (kind + area), linked
// (company / person), edited in place. Desktop is a two-pane reader — the list
// beside the reading pane; phone is master-detail. `area` locks the view to one
// area (the area-view Documents tab); unlocked, an area filter is offered.
const DOC_KINDS = ["docs", "internal"];
const DOC_AREAS = ["sales", "marketing", "operations", "rnd"];
// contact enums mirror schema.py (SEGMENTS/TIERS/LIFECYCLES/SOURCES) — the
// backend validates against these, so the inline "new person" form offers them.
const CONTACT_SEGMENTS = ["accounting", "erp", "ecommerce", "analytics", "consultancy", "other"];
const CONTACT_TIERS = ["A", "B", "C"];
const CONTACT_LIFECYCLES = ["none", "announced", "shipped", "operating"];
const CONTACT_SOURCES = ["warm", "trigger", "cold", "referral"];

// New-note view: type a title and Aito infers the rest (docs/25) — the company
// is mention-scanned against the entity, its people surface via the company_id
// link, topics are suggested from the store, and a context panel shows related
// prior notes. All inference is server-side (rule 2); the operator confirms.
const NOTE_DRAFT_KEY = "note-draft";
const blankNote = () => ({
  title: "", body: "", kind: "internal", area: "", company: "",
  stakeholder_id: "", topics: "",
  noted_on: new Date().toISOString().slice(0, 10),
});

export function NoteCreate() {
  const [optsReload, setOptsReload] = useState(0);   // bump to re-fetch after adding a person
  const opts = useAsync(() => api.todoOptions(), [optsReload]);
  const [newCo, setNewCo] = useState(false);         // inline "new company" open?
  const [newPerson, setNewPerson] = useState(false); // "new person" modal open?
  const [f, setF] = useState(blankNote);
  // once saved, the note is a real server document; `docId` reattaches to it so
  // further saves *update* it instead of forking a second note. This is the fix
  // for "Save note set up a new note and made the saved one disappear".
  const [docId, setDocId] = useState(null);
  const [dirty, setDirty] = useState(false);      // edits since the last server save
  const [recovered, setRecovered] = useState(false);
  const companyTouched = useRef(false);
  const [infer, setInfer] = useState(null);
  const [ctx, setCtx] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => { setF((p) => ({ ...p, [k]: e.target.value })); setDirty(true); };

  // Draft recovery: an in-progress note is mirrored to localStorage on every
  // edit, so an hour of meeting notes survives a closed tab, a clicked link, or
  // a dead laptop. Restore it once on mount (before typing overwrites state).
  useEffect(() => {
    try {
      const d = JSON.parse(localStorage.getItem(NOTE_DRAFT_KEY) || "null");
      if (d?.f && (d.f.title || d.f.body)) {
        setF({ ...blankNote(), ...d.f });
        setDocId(d.docId || null);
        setDirty(!d.docId || !!d.dirty);
        companyTouched.current = !!d.companyTouched;
        setRecovered(true);
      }
    } catch { /* ignore a corrupt draft */ }
  }, []);

  // autosave the draft (debounced) whenever there is content — the safety net
  useEffect(() => {
    if (!f.title.trim() && !f.body.trim()) return;
    const h = setTimeout(() => {
      try {
        localStorage.setItem(NOTE_DRAFT_KEY, JSON.stringify(
          { f, docId, dirty, companyTouched: companyTouched.current }));
      } catch { /* quota — best effort */ }
    }, 700);
    return () => clearTimeout(h);
  }, [f, docId, dirty]);

  // debounced inference on the title — company + people via the graph + topics
  useEffect(() => {
    if (!f.title.trim()) { setInfer(null); return; }
    const h = setTimeout(async () => {
      try {
        const r = await api.classifyDocument(f.title, {});
        setInfer(r);
        setF((p) => ({
          ...p,
          company: !companyTouched.current && r.companies?.length ? r.companies[0].name : p.company,
          stakeholder_id: p.stakeholder_id || (r.contacts?.[0]?.id ?? ""),
        }));
      } catch { /* best-effort only */ }
    }, 500);
    return () => clearTimeout(h);
  }, [f.title]);

  // debounced context — related prior notes (similar + same company)
  useEffect(() => {
    if (!f.title.trim()) { setCtx(null); return; }
    const h = setTimeout(async () => {
      try { setCtx(await api.documentContext(f.title, f.company || null)); } catch { /* best-effort */ }
    }, 650);
    return () => clearTimeout(h);
  }, [f.title, f.company]);

  if (opts.loading) return <Loading label="Loading…" />;
  if (opts.err) return <ErrorBox msg={opts.err} />;
  const contacts = opts.data.contacts || [];

  function addTopic(tp) {
    const cur = f.topics.split(";").map((s) => s.trim()).filter(Boolean);
    if (!cur.includes(tp)) { setF((p) => ({ ...p, topics: [...cur, tp].join(";") })); setDirty(true); }
  }
  function clearDraft() { try { localStorage.removeItem(NOTE_DRAFT_KEY); } catch { /* */ } }
  function reset() {
    clearDraft();
    setF(blankNote()); setDocId(null); setDirty(false); setRecovered(false);
    setInfer(null); setCtx(null); setErr(null); companyTouched.current = false;
  }
  async function save() {
    if (!f.title.trim() || !f.body.trim() || busy) return;
    setBusy(true); setErr(null);
    const payload = {
      title: f.title, body: f.body, kind: f.kind, area: f.area || null,
      company: f.company || null, stakeholder_id: f.stakeholder_id || null,
      topics: f.topics || null, noted_on: f.noted_on || null,
    };
    try {
      // ensure the company entity exists so the note's company_id link resolves
      // instead of dangling — idempotent, and independent of the ＋ New button
      if (f.company) { try { await api.createCompany(f.company); } catch { /* best effort */ } }
      let id = docId;
      if (id) await api.updateDocument(id, payload);
      else { const r = await api.createDocument(payload); id = r.doc_id; setDocId(id); }
      setDirty(false); setRecovered(false);
      // the note now lives on the server; keep it on screen (with an Open link)
      // and drop the local draft — it's superseded by the saved document.
      clearDraft();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  // Create a company entity inline and select it on the note (companyTouched so
  // inference won't overwrite the operator's explicit pick).
  async function onCompanyCreated(row) {
    setF((p) => ({ ...p, company: row.name })); companyTouched.current = true;
    setDirty(true); setNewCo(false);
  }
  // Create a contact inline; re-fetch the options so the new person is in the
  // select, and pre-select them (and adopt their company).
  async function onContactCreated(row) {
    setF((p) => ({ ...p, stakeholder_id: row.id, company: row.company || p.company }));
    companyTouched.current = true; setDirty(true);
    setOptsReload((n) => n + 1); setNewPerson(false);
  }
  // Related items link to the existing document (source_id == doc_id for docs),
  // so a near-duplicate is one click away — go update it instead of forking one.
  const openDoc = (id) => { window.location.hash = "/documents/" + id; };
  const relCount = (ctx?.same_company?.length || 0) + (ctx?.similar?.length || 0);

  return (
    <div className="note-create">
      {recovered && (
        <div className="nc-recovered">
          Recovered an unsaved draft.
          <button type="button" className="linklike" onClick={reset}>Discard &amp; start new</button>
        </div>
      )}
      <label className="fld">title
        <input className="nc-title" value={f.title} autoFocus
               placeholder="e.g. Acme meeting note" onChange={set("title")} /></label>
      {infer && (infer.companies?.length || infer.contacts?.length || infer.topics?.length) ? (
        <div className="nc-infer"><span className="pulse" /> Aito:
          {infer.companies?.length ? <> company <b>{infer.companies[0].name}</b></> : null}
          {infer.contacts?.length ? <> · {infer.contacts.length} contact(s) linked</> : null}
          {infer.topics?.length ? <> · topics {infer.topics.map((tp) =>
            <button key={tp} type="button" className="chip" onClick={() => addTopic(tp)}>{tp}</button>)}</> : null}
        </div>
      ) : null}
      {/* Related — a collapsible section that drops from under the title (not a
          right rail), so the body gets the full width. Items are links. */}
      <details className="nc-related" open={relCount > 0}>
        <summary>Related notes{relCount ? ` · ${relCount}` : ""}
          <span className="muted"> — open one to update it instead of duplicating</span></summary>
        {!ctx ? <div className="muted rel-empty">type a title to see related notes…</div> : (
          <div className="rel-body">
            <div className="rel-col">
              <div className="ctx-h">Same company</div>
              {ctx.same_company?.length ? ctx.same_company.map((n) =>
                <button key={n.doc_id} type="button" className="rel-item" onClick={() => openDoc(n.doc_id)}>
                  {n.title}{n.noted_on ? <span className="muted"> · {n.noted_on}</span> : null}</button>)
                : <div className="muted">none yet</div>}
            </div>
            <div className="rel-col">
              <div className="ctx-h">Similar</div>
              {ctx.similar?.length ? ctx.similar.map((h, i) =>
                <button key={h.source_id || i} type="button" className="rel-item"
                        disabled={!h.source_id} onClick={() => h.source_id && openDoc(h.source_id)}>
                  {h.title}</button>) : <div className="muted">none</div>}
            </div>
          </div>
        )}
      </details>
      <label className="fld nc-bodyfld">body
        <textarea className="nc-body" value={f.body} placeholder="# Heading&#10;markdown…"
                  onChange={set("body")} /></label>
      <div className="fld-row">
        <label className="fld">kind<select value={f.kind} onChange={set("kind")}>
          {DOC_KINDS.map((k) => <option key={k}>{k}</option>)}</select></label>
        <label className="fld">area<select value={f.area} onChange={set("area")}>
          <option value="">—</option>{DOC_AREAS.map((a) => <option key={a}>{a}</option>)}</select></label>
        <label className="fld">noted on<input type="date" value={f.noted_on} onChange={set("noted_on")} /></label>
      </div>
      <div className="fld-row">
        <label className="fld">company
          <div className="fld-with-add">
            <input value={f.company} placeholder="e.g. Acme"
                   onChange={(e) => { companyTouched.current = true; set("company")(e); }} />
            <button type="button" className="add-entity" title="add a new company"
                    onClick={() => setNewCo(true)}>＋ New</button>
          </div>
        </label>
        <label className="fld">person
          <div className="fld-with-add">
            <select value={f.stakeholder_id} onChange={set("stakeholder_id")}>
              <option value="">—</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
            </select>
            <button type="button" className="add-entity" title="add a new person"
                    onClick={() => setNewPerson(true)}>＋ New</button>
          </div>
        </label>
      </div>
      <label className="fld">topics<input value={f.topics} placeholder="a;b;c" onChange={set("topics")} /></label>
      {err && <div className="error">Save error: {err}</div>}
      <div className="nc-actions">
        <button className="primary" onClick={save}
                disabled={busy || !f.title.trim() || !f.body.trim() || (!!docId && !dirty)}>
          {busy ? "Saving…" : docId ? (dirty ? "Save changes" : "Saved ✓") : "Save note"}</button>
        {docId && (
          <button className="ghost" type="button" onClick={() => openDoc(docId)}>Open ↗</button>
        )}
        {(docId || f.title || f.body) && (
          <button className="linklike" type="button" onClick={reset}>＋ New note</button>
        )}
        {docId && !dirty && <span className="nc-savenote muted">saved to Documents</span>}
      </div>
      {newCo && <NewCompanyModal initialName={f.company}
                  onCreated={onCompanyCreated} onClose={() => setNewCo(false)} />}
      {newPerson && <NewContactModal initialCompany={f.company} contacts={contacts}
                  onCreated={onContactCreated} onClose={() => setNewPerson(false)} />}
    </div>
  );
}

// Inline "new company" — a company entity is just {company_id, name}, so this is
// a one-field modal. The backend slugs the name and is idempotent, so it's safe
// even if the company already exists (it just re-selects it).
function NewCompanyModal({ initialName, onCreated, onClose }) {
  const [name, setName] = useState(initialName || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  async function create() {
    if (!name.trim() || busy) return;
    setBusy(true); setErr(null);
    try { onCreated(await api.createCompany(name.trim())); }
    catch (e) { setErr(e.message); setBusy(false); }
  }
  return (
    <Modal onClose={onClose}>
      <h3>New company</h3>
      <label className="fld">name<input value={name} autoFocus placeholder="e.g. Acme"
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") create(); }} /></label>
      {err && <div className="error">{err}</div>}
      <div className="modal-actions">
        <span className="spacer" />
        <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="primary" onClick={create} disabled={busy || !name.trim()}>Create</button>
      </div>
    </Modal>
  );
}

// Inline "new person" — the rolodex validates segment/tier/lifecycle/source and
// requires every field (parse_rolodex_row), so the form offers those as selects
// with sensible defaults. The backend ensures the company entity exists first.
function NewContactModal({ initialCompany, contacts, onCreated, onClose }) {
  const [f, setF] = useState({
    name: "", company: initialCompany || "", role: "", country: "Finland",
    segment: "other", tier: "C", ai_lifecycle: "none", source: "cold",
    phone_present: false, email_present: false,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const chk = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.checked }));
  const ready = f.name.trim() && f.company.trim() && f.role.trim() && f.country.trim();
  async function create() {
    if (!ready || busy) return;
    setBusy(true); setErr(null);
    try { onCreated(await api.createContact({ ...f, notes_tags: [] })); }
    catch (e) { setErr(e.message); setBusy(false); }
  }
  return (
    <Modal onClose={onClose}>
      <h3>New person</h3>
      <div className="fld-row">
        <label className="fld">name<input value={f.name} autoFocus placeholder="e.g. Robin Aalto"
          onChange={set("name")} /></label>
        <label className="fld">company<input value={f.company} placeholder="e.g. Acme"
          onChange={set("company")} /></label>
      </div>
      <div className="fld-row">
        <label className="fld">role<input value={f.role} placeholder="e.g. CEO" onChange={set("role")} /></label>
        <label className="fld">country<input value={f.country} onChange={set("country")} /></label>
      </div>
      <div className="fld-row">
        <label className="fld">segment<select value={f.segment} onChange={set("segment")}>
          {CONTACT_SEGMENTS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="fld">tier<select value={f.tier} onChange={set("tier")}>
          {CONTACT_TIERS.map((s) => <option key={s}>{s}</option>)}</select></label>
      </div>
      <div className="fld-row">
        <label className="fld">AI lifecycle<select value={f.ai_lifecycle} onChange={set("ai_lifecycle")}>
          {CONTACT_LIFECYCLES.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="fld">source<select value={f.source} onChange={set("source")}>
          {CONTACT_SOURCES.map((s) => <option key={s}>{s}</option>)}</select></label>
      </div>
      <div className="fld-row nc-checks">
        <label className="chkfld"><input type="checkbox" checked={f.phone_present}
          onChange={chk("phone_present")} /> phone on file</label>
        <label className="chkfld"><input type="checkbox" checked={f.email_present}
          onChange={chk("email_present")} /> email on file</label>
      </div>
      {err && <div className="error">{err}</div>}
      <div className="modal-actions">
        <span className="spacer" />
        <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="primary" onClick={create} disabled={busy || !ready}>Create person</button>
      </div>
    </Modal>
  );
}

// free-text match over a loaded document (title / company / person / topics /
// body) — the Documents view's own filter, so notes are findable where they open.
function docMatch(d, q) {
  const s = q.toLowerCase();
  return [d.title, d.company_eff, d.company, d.contact_name, d.topics, d.body]
    .some((v) => (v || "").toLowerCase().includes(s));
}

export function Documents({ area = null, openDoc = null }) {
  const [reload, setReload] = useState(0);
  const [kind, setKind] = useState("");
  const [areaF, setAreaF] = useState("");
  const [sel, setSel] = useState(openDoc);        // selected doc_id (deep-link or click)
  const [q, setQ] = useState("");                  // free-text filter over loaded docs
  const [editing, setEditing] = useState(null);   // doc | "new" | null
  const phone = useIsPhone();
  const areaEff = area || areaF;                   // the prop locks the area
  const params = {};
  if (kind) params.kind = kind;
  if (areaEff) params.area = areaEff;
  const list = useAsync(() => api.documents(params), [kind, areaEff, reload]);
  const refresh = () => setReload((n) => n + 1);

  const filters = (
    <div className="doc-filters">
      <div className="chips">
        <Chip on={!kind} onClick={() => setKind("")}>all</Chip>
        {DOC_KINDS.map((k) => <Chip key={k} on={kind === k} onClick={() => setKind(k)}>{k}</Chip>)}
      </div>
      {!area && (
        <div className="chips">
          <Chip on={!areaF} onClick={() => setAreaF("")}>any area</Chip>
          {DOC_AREAS.map((a) => <Chip key={a} on={areaF === a} onClick={() => setAreaF(a)}>{a}</Chip>)}
        </div>
      )}
      <input className="doc-search" value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="filter notes… (title, company, topic, text)" />
      <span className="spacer" />
      <button className="new-todo" onClick={() => setEditing("new")}>+ New document</button>
    </div>
  );

  let inner;
  if (list.loading) inner = <Loading label="Loading documents…" />;
  else if (list.err) inner = <ErrorBox msg={list.err} />;
  else {
    const all = list.data.documents;
    const docs = q.trim() ? all.filter((d) => docMatch(d, q.trim())) : all;
    const active = docs.find((d) => d.doc_id === sel) || (phone ? null : docs[0]);
    if (!docs.length) inner = <div className="empty">
      {q.trim() ? `no notes match “${q.trim()}”` : `no documents${areaEff ? ` in ${areaEff}` : ""} yet`}</div>;
    else if (phone && active) inner = (
      <div className="doctree phone-doc">
        <button className="doc-back" onClick={() => setSel(null)}>← All documents</button>
        <DocumentPane doc={active} onEdit={() => setEditing(active)} />
      </div>
    );
    else inner = (
      <div className="doctree">
        <DocumentList docs={docs} active={active} onOpen={(d) => setSel(d.doc_id)} />
        {!phone && active && <DocumentPane doc={active} onEdit={() => setEditing(active)} />}
      </div>
    );
  }

  return (
    <>
      {filters}
      {inner}
      {editing && <DocumentEditor
        doc={editing === "new" ? { area: areaEff || null } : editing}
        lockedArea={area} onClose={() => setEditing(null)}
        onSaved={(id) => { setEditing(null); if (id) setSel(id); refresh(); }} />}
    </>
  );
}

function DocBadges({ doc }) {
  return (
    <span className="doc-badges">
      <span className={"doc-kind k-" + doc.kind}>{doc.kind}</span>
      {doc.area && <span className="doc-area">{doc.area}</span>}
      {doc.company_eff && <span className="doc-co">{doc.company_eff}</span>}
      {doc.contact_name && <span className="doc-person">{doc.contact_name}</span>}
    </span>
  );
}

function DocumentList({ docs, active, onOpen }) {
  return (
    <div className="doclist">
      {docs.map((d) => (
        <button key={d.doc_id}
                className={"docitem" + (active && d.doc_id === active.doc_id ? " active" : "")}
                onClick={() => onOpen(d)}>
          <div className="dt">{d.title}</div>
          <DocBadges doc={d} />
        </button>
      ))}
    </div>
  );
}

function DocumentPane({ doc, onEdit }) {
  return (
    <div className="docpane panel">
      <div className="docpane-h">
        <DocBadges doc={doc} />
        <span className="spacer" />
        <span className="doc-updated">updated {doc.updated}</span>
        <button className="doc-edit" title="edit this document" onClick={onEdit}>✎ Edit</button>
      </div>
      <Markdown text={doc.body} />
    </div>
  );
}

function DocumentEditor({ doc, lockedArea, onClose, onSaved }) {
  const opts = useAsync(() => api.todoOptions(), []);
  const isNew = !doc.doc_id;
  const [f, setF] = useState({
    title: doc.title || "", body: doc.body || "", kind: doc.kind || "internal",
    area: doc.area || "", company: doc.company || "", stakeholder_id: doc.stakeholder_id || "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [confirm, setConfirm] = useState(false);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  async function save() {
    setBusy(true); setErr(null);
    const payload = { title: f.title, body: f.body, kind: f.kind,
      area: f.area || null, company: f.company || null, stakeholder_id: f.stakeholder_id || null };
    try {
      if (isNew) { const r = await api.createDocument(payload); onSaved(r.doc_id); }
      else { await api.updateDocument(doc.doc_id, payload); onSaved(doc.doc_id); }
    } catch (e) { setErr(e.message); setBusy(false); }
  }
  async function remove() {
    setBusy(true); setErr(null);
    try { await api.deleteDocument(doc.doc_id); onSaved(null); }
    catch (e) { setErr(e.message); setBusy(false); }
  }
  if (opts.loading) return <Modal onClose={onClose}><Loading label="Loading form…" /></Modal>;
  if (opts.err) return <Modal onClose={onClose}><ErrorBox msg={opts.err} /></Modal>;
  return (
    <Modal onClose={onClose}>
      <h3>{isNew ? "New document" : "Edit document"}</h3>
      <label className="fld">title<input value={f.title} onChange={set("title")} autoFocus /></label>
      <label className="fld">body<textarea value={f.body} onChange={set("body")} rows={10}
                                            placeholder="# Heading&#10;markdown…" /></label>
      <div className="fld-row">
        <label className="fld">kind<select value={f.kind} onChange={set("kind")}>
          {DOC_KINDS.map((k) => <option key={k}>{k}</option>)}</select></label>
        <label className="fld">area<select value={f.area} onChange={set("area")} disabled={!!lockedArea}>
          <option value="">—</option>
          {DOC_AREAS.map((a) => <option key={a}>{a}</option>)}</select></label>
      </div>
      <div className="fld-row">
        <label className="fld">company<input value={f.company} onChange={set("company")}
                                             placeholder="e.g. Northwind" /></label>
        <label className="fld">person<select value={f.stakeholder_id} onChange={set("stakeholder_id")}>
          <option value="">—</option>
          {opts.data.contacts.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
        </select></label>
      </div>
      {err && <div className="error">Save error: {err}</div>}
      <div className="modal-actions">
        {!isNew && (confirm
          ? <button className="nogo" onClick={remove} disabled={busy}>Confirm delete</button>
          : <button className="ghost" onClick={() => setConfirm(true)} disabled={busy}>Delete</button>)}
        <span className="spacer" />
        <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="primary" onClick={save}
                disabled={busy || !f.title.trim() || !f.body.trim()}>Save</button>
      </div>
    </Modal>
  );
}

// ---- Smart search (unified index over content; Aito text-match ranking) ----
const SEARCH_KINDS = ["doc", "contact", "deal"];

// Global quick-find in the top row: a literal jump-to across companies, notes,
// todos, contacts (docs/25). Distinct from the ranked Search view — this opens
// things fast via the deep-link routes. Results dropdown; Enter opens the first.
export function QuickFind() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); setOpen(false); return; }
    const h = setTimeout(async () => {
      try { setRes(await api.quickFind(q)); setOpen(true); } catch { setRes(null); }
    }, 250);
    return () => clearTimeout(h);
  }, [q]);
  const groups = res?.groups || [];
  const first = groups[0]?.items?.[0];
  const go = (target) => { setQ(""); setRes(null); setOpen(false); window.location.hash = "/" + target; };
  return (
    <div className="quickfind">
      <input className="qf-input" value={q} placeholder="Find… companies, notes, todos"
             onChange={(e) => setQ(e.target.value)}
             onFocus={() => { if (res) setOpen(true); }}
             onBlur={() => setTimeout(() => setOpen(false), 150)}
             onKeyDown={(e) => {
               if (e.key === "Escape") setOpen(false);
               if (e.key === "Enter" && first) go(first.target);
             }} />
      {open && res && (
        <div className="qf-drop">
          {groups.length === 0
            ? <div className="qf-empty">no matches for “{res.query}”</div>
            : groups.map((g) => (
              <div key={g.kind} className="qf-group">
                <div className="qf-gl">{g.kind}</div>
                {g.items.map((it, i) => (
                  <button key={i} className={"qf-item k-" + g.kind}
                          onMouseDown={() => go(it.target)}>
                    <span className="qf-label">{it.label}</span>
                    {it.sub && <span className="qf-sub">{it.sub}</span>}
                  </button>
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// The knowledge graph (docs/31): one card per question a person actually asks,
// each showing the single Aito query that answered it. The query is on screen
// on purpose — the claim of this view is that the question and the query are
// nearly the same sentence once the facts live on the company node and the
// links are walkable.
function GraphAnswer({ a }) {
  // Aito returns hit keys sorted alphabetically, which reads badly ("country,
  // industry, mrr_eur, name"). Take the column order from the query's own
  // `select` instead — an entry is either a plain field or a {alias: expr}
  // object — and append anything the response carried that select didn't name.
  const present = a.hits && a.hits.length ? Object.keys(a.hits[0]) : [];
  const asked = (a.request && Array.isArray(a.request.select) ? a.request.select : [])
    .map((c) => (typeof c === "string" ? c : Object.keys(c)[0]));
  const cols = [
    ...asked.filter((c) => present.includes(c)),
    ...present.filter((c) => !asked.includes(c)),
  ];
  return (
    <div className="gq-card">
      <div className="gq-q">{a.question}</div>
      <pre className="gq-query">{JSON.stringify(a.request, null, 1)}</pre>
      {a.why && a.why.length > 0 && (
        <div className="gq-why">
          <div className="gq-p">
            <span className="gq-pnum">{Math.round(a.p * 100)}%</span>
            <span className="gq-plabel">probability of winning</span>
          </div>
          {/* Each factor's bar runs from the centre: right of it the fact made
              winning MORE likely, left of it less. Width is log-scaled because
              lift is multiplicative — x2 and x0.5 are the same size of effect
              in opposite directions, and a linear bar hides that. */}
          {a.why.map((f) => {
            const mag = Math.min(1, Math.abs(Math.log2(f.lift)) / 1.5);
            const up = f.lift >= 1;
            return (
              <div className="gq-factor" key={f.label}>
                <span className="gq-flabel" title={f.label}>{f.label}</span>
                <span className="gq-track">
                  <span className={"gq-bar " + (up ? "up" : "down")}
                        style={{ width: `${mag * 50}%`, [up ? "left" : "right"]: "50%" }} />
                  <span className="gq-mid" />
                </span>
                <span className={"gq-lift " + (up ? "up" : "down")}>×{f.lift.toFixed(2)}</span>
              </div>
            );
          })}
        </div>
      )}
      {a.error ? (
        <div className="gq-err">{a.error}</div>
      ) : (
        <>
          <div className="gq-meta">
            {a.total} {a.total === 1 ? "row" : "rows"}
            {a.hits && a.total > a.hits.length ? ` · showing ${a.hits.length}` : ""}
          </div>
          {cols.length === 0 ? (
            <div className="gq-empty">no rows</div>
          ) : (
            <table className="gq-table">
              <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {a.hits.map((h, i) => (
                  <tr key={i}>
                    {cols.map((c) => (
                      <td key={c} className={typeof h[c] === "number" ? "num" : ""}>
                        {typeof h[c] === "number" && c === "$p"
                          ? Math.round(h[c] * 100) + "%"
                          : String(h[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}

export function GraphView() {
  const r = useAsync(() => api.graph(), []);
  return (
    <>
      <div className="gq-intro">
        The company is a <b>node</b>; contacts, deals and documents link to it.
        Aito walks those links in both directions — <code>company_id.industry</code>{" "}
        forward to the account, <code>$refs.contacts.company_id</code> back to its
        people — so each question below is <b>one query</b>, not a join.
        {r.data && r.data.conditioned_p != null && r.data.baseline_p != null && (
          <div className="gq-finding">
            And the neighbourhood can condition a <b>prediction</b>: a deal at an
            account where we know a CTO closes at{" "}
            <b>{Math.round(r.data.conditioned_p * 100)}%</b>, against a{" "}
            {Math.round(r.data.baseline_p * 100)}% base rate across all deals.
            Whether a CTO is on file exists nowhere on the deal — only across the
            link. Both figures come from the queries on this page.
          </div>
        )}
      </div>
      {r.loading && <Loading label="Asking the graph…" />}
      {r.err && <ErrorBox msg={r.err} />}
      {r.data && (
        <>
          {r.data.failed && r.data.failed.length > 0 && (
            <div className="gq-warn">
              {r.data.failed.length} of {r.data.answers.length} queries failed: {r.data.failed.join(", ")}
            </div>
          )}
          <div className="gq-grid">
            {r.data.answers.map((a) => <GraphAnswer key={a.id} a={a} />)}
          </div>
        </>
      )}
    </>
  );
}

export function SearchView({ initial }) {
  // `#/search/<query>` runs that search on arrival, so a search is a shareable
  // link rather than something only a keyboard can reach.
  const seeded = initial ? decodeURIComponent(initial) : "";
  // ?kind=doc alongside the query, so a shared link carries the filter too —
  // without it the largest collection (deals) crowds out everything else.
  const seededKind = typeof window === "undefined" ? ""
    : new URLSearchParams(window.location.search).get("kind") || "";
  const [text, setText] = useState(seeded);
  const [kind, setKind] = useState(seededKind);
  const [query, setQuery] = useState(seeded);   // the submitted query
  const [clicked, setClicked] = useState({}); // item_id -> true, once recorded
  const r = useAsync(
    () => (query ? api.search(query, kind) : Promise.resolve(null)),
    [query, kind]);
  const submit = (e) => { e.preventDefault(); setClicked({}); setQuery(text.trim()); };
  // recording a click is the training signal (docs/23): it lifts this item for
  // similar queries next time. Fire-and-forget; the ranking updates server-side.
  const open = (ctx, id) => {
    if (!ctx || clicked[id]) return;
    setClicked((c) => ({ ...c, [id]: true }));
    api.searchClick(ctx, id).catch(() => {});
  };
  return (
    <>
      <form className="search-bar" onSubmit={submit}>
        <input className="search-input" value={text} autoFocus
               placeholder="Search docs, contacts, deals…"
               onChange={(e) => setText(e.target.value)} />
        <select className="qa-field" value={kind} onChange={(e) => setKind(e.target.value)} title="kind">
          <option value="">all kinds</option>
          {SEARCH_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <button className="qa-add" type="submit" disabled={!text.trim()}>Search</button>
      </form>
      {!query && <div className="empty">type a query — results are ranked by Aito text-match relevance</div>}
      {query && r.loading && <Loading label="Searching…" />}
      {query && r.err && <ErrorBox msg={r.err} />}
      {query && r.data && (
        r.data.count === 0
          ? <div className="empty">no matches for “{r.data.query}”</div>
          : <>
              <div className="section-title">{r.data.count} results for “{r.data.query}”, most relevant first</div>
              <div className="sr-list">
                {r.data.hits.map((h, i) => (
                  <button className={"sr-row" + (clicked[h.item_id] ? " picked" : "")} key={h.item_id}
                          title={h.kind === "doc" ? "open the note (and train the ranking)"
                                                  : "mark useful — trains the ranking"}
                          onClick={() => {
                            open(r.data.context_id, h.item_id);
                            if (h.kind === "doc") window.location.hash = "/documents/" + h.source_id;
                          }}>
                    <span className="sr-rank">{i + 1}</span>
                    <span className={"sr-kind k-" + h.kind}>{h.kind}</span>
                    <span className="sr-title">{h.title}</span>
                    {h.tags && <span className="sr-tags">{h.tags.split(";").filter(Boolean).slice(0, 3).join(" · ")}</span>}
                    {clicked[h.item_id] && <span className="sr-check">✓</span>}
                  </button>
                ))}
              </div>
              {r.data.semantic && (
                <div className="sr-note">
                  matched by meaning as well as words — the query was embedded and
                  compared against the index, so a result need share no term with it
                </div>
              )}
              {r.data.learned && <div className="sr-note">ranking trained by past clicks</div>}
            </>
      )}
    </>
  );
}

// ---- Chat (the assistant as a full-page view, with several conversations) ----
// The durable home for the assistant: chat-first, with a "Chats (N)" history
// you open on demand — a scrollable list of every past conversation, kept in
// the shared store (localStorage) so nothing is lost on close/reload, only on
// an explicit (two-tap) delete. Shares threads with the quick ✦ panel. Same
// bounded, Aito-backed tool loop (rule 1b); Stop included.
function relTime(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return Math.floor(s / 60) + "m";
  if (s < 86400) return Math.floor(s / 3600) + "h";
  return Math.floor(s / 86400) + "d";
}

export function ChatView() {
  const state = useConversations();
  const active = conversations.active();
  const [browsing, setBrowsing] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const open = (id) => { conversations.select(id); setBrowsing(false); };
  const newChat = () => { conversations.create(); setBrowsing(false); };
  const threads = [...state.threads].sort((a, b) => b.updated - a.updated);

  if (browsing) {
    return (
      <div className="chatview">
        <div className="chat-list">
          <button className="new-todo" onClick={newChat}>+ New chat</button>
          {threads.map((t) => (
            <div key={t.id} className={"chat-row" + (t.id === active.id ? " on" : "")}
                 onClick={() => open(t.id)}>
              <span className="cr-title">{t.title}</span>
              <span className="cr-time">{relTime(t.updated)}</span>
              <button className={"ct-del" + (confirmDel === t.id ? " confirm" : "")}
                      title="delete conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirmDel === t.id) { conversations.remove(t.id); setConfirmDel(null); }
                        else setConfirmDel(t.id);
                      }}>
                {confirmDel === t.id ? "remove?" : "×"}
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="chatview">
      <div className="chat-bar">
        <button className="chat-hist" onClick={() => { setConfirmDel(null); setBrowsing(true); }}>
          ☰ Chats ({state.threads.length})
        </button>
        <span className="chat-cur" title={active.title}>{active.title}</span>
        <button className="new-todo" onClick={newChat}>+ New</button>
      </div>
      <div className="chat-active">
        <ChatThread key={active.id} msgs={active.msgs}
                    setMsgs={(m) => conversations.setMsgs(active.id, m)} />
      </div>
    </div>
  );
}

// ---- Activity (the change log: what was created / updated / done / won / lost) ----
// A read-only feed over the changelog table (docs/22); the same audit the
// assistant can query, and the raw material for future
// daily/weekly note roll-ups.
export function Activity() {
  const r = useAsync(() => api.changelog(), []);
  const changes = r.data?.changes || [];
  return (
    <div className="activity">
      {r.loading && !r.data ? <Loading label="Loading activity…" />
        : r.err ? <ErrorBox msg={r.err} />
        : changes.length === 0
          ? <div className="empty">no activity yet — it fills in as you and the agent create and update things</div>
          : <div className="act-list">
              {changes.map((c, i) => (
                <div className="act-row" key={i}>
                  <span className={"act-tag a-" + c.action}>{c.action}</span>
                  <span className="act-entity">{c.entity}</span>
                  <span className="act-summary">{c.summary}</span>
                  <span className="act-time">{relTime(Date.parse(c.at))}</span>
                </div>
              ))}
            </div>}
    </div>
  );
}

// ---- the views keyed by nav id ----
// ---- Sales analytics (parity with marketing metrics) ----
// KPIs + close-likelihood come from Aito (deals.pipeline / who_to_reach); the
// stage rollup below is arithmetic over those results (counts, sums, and the
// mean of Aito's per-deal p_win), which is formatting, not inference (rule 2).
const SALES_STAGE_ORDER = ["lead", "qualified", "demo", "pilot", "negotiation"];

function stageBreakdown(deals) {
  const m = {};
  for (const d of deals) {
    const s = (m[d.stage] ||= { count: 0, value: 0, psum: 0, pn: 0 });
    s.count += 1; s.value += d.value_eur;
    if (d.p_win != null) { s.psum += d.p_win; s.pn += 1; }
  }
  const rows = SALES_STAGE_ORDER.filter((k) => m[k]).map((k) => ({
    stage: k, count: m[k].count, value: m[k].value,
    avgP: m[k].pn ? m[k].psum / m[k].pn : null,
  }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  return rows.map((r) => ({ ...r, frac: r.value / max }));
}

// Lazy close-likelihood: /api/deals paints instantly (aggregates + stalled),
// then each DISTINCT deal profile (stage|blocker|champion) resolves in parallel
// via /api/pwin and fills in. Cached in a module Map, so it's instant on
// re-navigation within the session; the graph shares the same cache.
const pwinCache = new Map();
const pwinKey = (d) => `${d.stage}|${d.blocker}|${d.champion_present}`;
function usePwin(deals) {
  const [, bump] = useState(0);
  useEffect(() => {
    let alive = true;
    const pending = new Set();
    for (const d of deals || []) {
      if (d.p_win != null) continue;               // already resolved (predict=True path)
      const k = pwinKey(d);
      if (pwinCache.has(k) || pending.has(k)) continue;
      pending.add(k);
      api.pwin(d.stage, d.blocker, d.champion_present)
        .then((r) => { if (alive) { pwinCache.set(k, r); bump((n) => n + 1); } })
        .catch(() => {});
    }
    return () => { alive = false; };
  }, [deals]);
  return (deals || []).map((d) => {
    if (d.p_win != null) return d;
    const c = pwinCache.get(pwinKey(d));
    return c ? { ...d, p_win: c.p_win, why: c.why } : d;
  });
}

function WhoToReach() {
  const r = useAsync(() => api.whoToReach(), []);
  const rows = usePwin(r.data?.rows);   // fill p_win lazily from the shared cache
  if (r.loading) return <Loading />;
  if (r.err) return <ErrorBox msg={r.err} />;
  if (!rows.length) return <div className="empty">No stalled deals — the pipeline is warm.</div>;
  const ranked = [...rows].sort((a, b) => (b.p_win ?? -1) - (a.p_win ?? -1)).slice(0, 8);
  return (
    <div className="co-list">
      {ranked.map((row) => {
        const who = row.contacts[0];
        const pw = row.p_win == null ? null : Math.round(row.p_win * 100);
        return (
          <div className="co-row" key={row.deal_id}>
            <div>
              <div className="co-name">{row.company}</div>
              <div className="co-sub">{who ? who.name : "—"} · {row.stage} · <span className="down">{row.days_since_touch}d cold</span></div>
            </div>
            <div className="co-deals">
              <span className={"co-eur " + (pw != null && pw >= 50 ? "up" : "")}>{pw != null ? pw + "%" : "–"}</span>
              <span className="co-dsub">P(won)</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SalesAnalytics() {
  const pipe = useAsync(() => api.deals(), []);
  const trend = useAsync(() => api.salesTrend(), []);
  const deals = usePwin(pipe.data?.deals);
  if (pipe.loading) return <Loading />;
  if (pipe.err) return <ErrorBox msg={pipe.err} />;
  const { kpis } = pipe.data;
  const stages = stageBreakdown(deals);
  const t = trend.data;
  return (
    <>
      <KpiRow items={[
        { label: "win rate", value: t ? pct(t.win_rate) : "…", sub: t ? `${t.won}/${t.closed} closed` : "" },
        { label: "weighted pipeline", value: eur(kpis.weighted_pipeline), sub: "P(won) · value" },
        { label: "open value", value: eur(kpis.open_value), sub: `${kpis.open_deals} open` },
        { label: "avg cycle", value: t ? t.avg_cycle_days + "d" : "…", sub: "won deals" },
        { label: "stalled", value: kpis.stalled, sub: "no touch > 14d" },
      ]} />
      {t && t.quarters.length > 0 && (
        <Block title="Win rate by quarter" ptype="trend">
          <QuarterBars series={t.quarters} />
        </Block>
      )}
      <div className="cols">
        <Block title="Pipeline by stage" ptype="predict">
          <div className="list">
            {stages.map((s) => (
              <BarRow key={s.stage} name={`${s.stage} · ${s.count}`} p={s.frac}
                      num={`${eur(s.value)}${s.avgP != null ? " · win " + pct(s.avgP) : ""}`}
                      dir={s.avgP != null && s.avgP >= 0.5 ? "up" : ""} />
            ))}
          </div>
        </Block>
        <Block title="Who to reach now" ptype="who_to_reach">
          <WhoToReach />
        </Block>
      </div>
      <FunnelView only="sales" />
    </>
  );
}

// ---- Overview: the KPI-forward home (sales + a marketing top-line) ----
function Overview() {
  const pipe = useAsync(() => api.deals(), []);
  const trend = useAsync(() => api.salesTrend(), []);
  const web = useAsync(() => api.funnel("website", {}), []);
  const deals = usePwin(pipe.data?.deals);
  if (pipe.loading) return <Loading />;
  if (pipe.err) return <ErrorBox msg={pipe.err} />;
  const { kpis } = pipe.data;
  const t = trend.data;
  const stages = stageBreakdown(deals);
  const paid = web.data?.stages?.slice(-1)[0]?.count;
  return (
    <>
      <KpiRow items={[
        { label: "weighted pipeline", value: eur(kpis.weighted_pipeline), sub: "P(won) · value" },
        { label: "win rate", value: t ? pct(t.win_rate) : "…", sub: t ? `${t.won}/${t.closed} closed` : "" },
        { label: "open deals", value: kpis.open_deals, sub: eur(kpis.open_value) },
        { label: "avg cycle", value: t ? t.avg_cycle_days + "d" : "…", sub: "won deals" },
        { label: "paid conversions", value: paid ?? "…", sub: "website funnel" },
        { label: "stalled", value: kpis.stalled, sub: "no touch > 14d" },
      ]} />
      {t && t.quarters.length > 0 && (
        <Block title="Win rate by quarter" ptype="trend"><QuarterBars series={t.quarters} /></Block>
      )}
      <div className="cols">
        <Block title="Pipeline by stage" ptype="predict">
          <div className="list">
            {stages.map((s) => (
              <BarRow key={s.stage} name={`${s.stage} · ${s.count}`} p={s.frac}
                      num={`${eur(s.value)}${s.avgP != null ? " · win " + pct(s.avgP) : ""}`}
                      dir={s.avgP != null && s.avgP >= 0.5 ? "up" : ""} />
            ))}
          </div>
        </Block>
        <Block title="Who to reach now" ptype="who_to_reach"><WhoToReach /></Block>
      </div>
    </>
  );
}

export const VIEWS = {
  overview: { title: "Overview", desc: "Where the business stands — pipeline, win rate, conversion, and who to reach next. Every rate and likelihood is an Aito prediction.",
           prims: ["kpi-row", "predict", "chart"],
           data: [{ table: "deals" }],
           render: () => <Overview /> },
  chat:  { title: "Chat", desc: "Ask the system in a full conversation — grounded in Aito, every number from a tool call. Keep several threads going; the quick ✦ panel shares them.",
           prims: ["assistant"],
           render: () => <ChatView /> },
  now:   { title: "Now", desc: "The most urgent actions across every area.",
           prims: ["action-pipeline"],
           data: [{ table: "todos", label: "all todos" }],
           render: () => <Block title="Do next" ptype="action-pipeline"><NowAction /></Block> },
  sales: { title: "Sales", desc: "The sales to-do list, the pipeline, the companies behind it, this week's calls, and the funnel.",
           prims: ["action-pipeline", "action-calendar", "kpi-row", "chart"],
           data: [{ table: "deals" }, { table: "contacts" }, { table: "touches" }],
           docsArea: "sales",
           tabs: [
             { id: "todo", label: "To do",
               render: () => <Block title="Sales to-do" ptype="action-pipeline"><AreaAction area="sales" lens="pipeline" /></Block> },
             { id: "pipeline", label: "Pipeline",
               render: () => <Block title="Pipeline" ptype="kpi-row"><Deals /></Block> },
             { id: "companies", label: "Companies",
               render: () => <Companies /> },
             { id: "calls", label: "Calls",
               render: () => <Block title="This week" ptype="action-calendar"><AreaAction area="sales" lens="calendar" /></Block> },
             { id: "funnel", label: "Funnel",
               render: () => <FunnelView only="sales" /> },
           ] },
  marketing: { title: "Marketing", desc: "What to ship to which channel, the go/no-go board, then the formula behind reach.",
           prims: ["action-calendar", "kpi-row", "chart", "optimizer"],
           data: [{ table: "posts" }, { table: "materials" }, { table: "channels" }, { table: "sessions" }],
           docsArea: "marketing",
           render: () => (<>
             <Block title="This week" ptype="action-calendar"><AreaAction area="marketing" lens="calendar" /></Block>
             <Block title="Posts — material × channel" ptype="kpi-row"><PostsBoard /></Block>
             <FunnelView only="website" />
             <Block title="Post scorer" ptype="optimizer"><Scorer /></Block></>) },
  mywork: { title: "My work", desc: "The leads, deals, and tasks assigned to you — your focused lane over the shared CRM. Reassign here; the operator or the agent can assign to anyone.",
           prims: ["kpi-row", "action-pipeline"],
           render: () => <MyWork /> },
  admin: { title: "Admin", desc: "Manage the team: add users (their Microsoft-account email + role), change roles, deactivate. Operator only.",
           prims: ["action-pipeline"],
           render: () => <UsersAdmin /> },
  routines: { title: "Routines", desc: "Recurring tasks on a cadence — due when their period comes up. Prepare runs the agentic prep (Aito candidates + a Claude prompt).",
           prims: ["kpi-row", "action-pipeline"],
           data: [{ table: "routines" }],
           render: () => <Routines /> },
  events: { title: "Events", desc: "Events to attend, each with a go/no-go decision; the ones you're going to show on the calendar.",
           prims: ["kpi-row", "action-calendar", "action-pipeline"],
           data: [{ table: "events" }],
           render: () => <Events /> },
  ops:   { title: "Operations", desc: "Running instances and obligations, by priority — with a week calendar for the deadlines (renewals, reports).",
           prims: ["action-calendar", "action-pipeline"],
           data: [{ table: "todos", where: { area: "operations" }, label: "operations todos" }],
           docsArea: "operations",
           render: () => <Block title="By priority" ptype="action-pipeline"><AreaAction area="operations" lens="pipeline" /></Block> },
  rnd:   { title: "R&D", desc: "Product workstreams, by priority.",
           prims: ["action-pipeline"],
           data: [{ table: "todos", where: { area: "rnd" }, label: "R&D todos" }],
           docsArea: "rnd",
           render: () => <Block title="By priority" ptype="action-pipeline"><AreaAction area="rnd" lens="pipeline" /></Block> },
  exp:   { title: "Learning", desc: "Build → Measure → Learn. The validated-learning rate, the running bets, and which kinds of experiment tend to pay off.",
           prims: ["kpi-row", "predict", "action-pipeline"],
           data: [{ table: "experiments" }],
           render: () => (<>
             <Experiments />
             <Block title="Learning actions" ptype="action-pipeline"><AreaAction area="experiments" lens="pipeline" /></Block></>) },
  activity: { title: "Activity", desc: "The change log — everything created and updated across the system (a todo done, a deal won or lost), newest first. The same audit the assistant can read.",
           prims: ["document-tree"],
           render: () => <Activity /> },
  documents: { title: "Documents", desc: "The knowledge store — strategy, plans, notes, and reference the agent grounds on. Tagged by kind and area, linked to companies and people, edited in place.",
           prims: ["document-store"],
           render: (param) => <Block title="Documents" ptype="document-store"><Documents openDoc={param} /></Block> },
  note: { title: "New note", desc: "Type a title and Aito infers the rest — the company (mention-scanned against the entity), its people (via the company_id link), suggested topics, and a diary date — with related prior notes for context. You confirm before saving.",
           prims: ["aito-inference"],
           render: () => <NoteCreate /> },
  company: { title: "Company", desc: "One company node — its people, deals, and notes, linked through the entity graph. Open a note to read it.",
           prims: ["entity-node"],
           render: (param) => <CompanyDetail companyId={param} /> },
  graph: { title: "Knowledge graph", desc: "What we know about each account — and the questions you can answer by walking the links between accounts, people and deals. Every card is one Aito query.",
           prims: ["graph-query"],
           render: () => <GraphView /> },
  search: { title: "Search", desc: "Smart search across content — docs, contacts, and deals — ranked by Aito text-match relevance. The same index the assistant grounds on.",
           prims: ["document-tree"],
           render: (param) => <SearchView initial={param} /> },
  salesanalytics: { title: "Sales analytics", desc: "Pipeline health, close-likelihood by stage, who to reach, and the sales funnel with its lever — the sales counterpart to the marketing metrics.",
           prims: ["kpi-row", "predict", "chart"],
           data: [{ table: "deals" }, { table: "contacts" }],
           render: () => <SalesAnalytics /> },
  analytics: { title: "Analytics", desc: "Segments, funnels, and the levers that move them.",
           prims: ["kpi-row", "chart"],
           render: () => (<><Segment360 /><FunnelView /></>) },
  decisions: { title: "Decisions", desc: "Agent recommended → you decided. Is the agent's confidence trustworthy?",
           prims: ["kpi-row"],
           data: [{ table: "decisions" }],
           render: () => <Decisions /> },
  data: { title: "Data", desc: "Every row of any table as a sheet — the whole pipeline, old cases and all.",
           prims: ["sheet"],
           render: () => <DataView /> },
};
