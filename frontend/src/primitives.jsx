// The view primitives, rev 3 §1.3. A view composes these; each takes a
// single props contract. Only the primitives we can back with real Aito
// data today are implemented (kpi-row, chart→funnel, optimizer); the
// action/document primitives arrive with the todos/library tables.
import React, { useEffect, useRef, useState } from "react";
import { now as clockNow } from "./clock.js";
import { publicDemo } from "./session.js";
import { pct } from "./api.js";

export function Block({ title, ptype, note, children }) {
  return (
    <section className="block">
      <div className="block-head">
        <h2>{title}</h2>
        {note && <span className="note">{note}</span>}
      </div>
      {children}
    </section>
  );
}

// default label fits the common case (a view backed by an Aito query); pass a
// label for surfaces with their own wording (e.g. "Loading documents…").
export function Loading({ label = "Querying Aito…" }) { return <div className="loading">{label}</div>; }
export function ErrorBox({ msg }) { return <div className="error">Aito error: {msg}</div>; }

// true when the viewport is at or below `max` px, reactive to resize/rotate.
// Used to switch two-pane layouts (e.g. Documents) to a phone master-detail.
export function useIsPhone(max = 880) {
  const query = `(max-width: ${max}px)`;
  const [phone, setPhone] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setPhone(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [query]);
  return phone;
}

// async data hook: returns {data, err, loading}, refetches when deps change
export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let live = true;
    // stale-while-revalidate: keep the previous data visible during a refetch
    // so re-fetching doesn't blank the view.
    setState((s) => ({ ...s, loading: true }));
    fn().then(
      (data) => live && setState({ data, loading: false }),
      (err) => live && setState({ err: err.message, loading: false })
    );
    return () => { live = false; };
  }, deps); // eslint-disable-line
  return state;
}

export function Select({ label, value, options, onChange, allowAll }) {
  return (
    <div className="field">
      <label>{label.replace(/_/g, " ")}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {allowAll && <option value="">All</option>}
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

// kpi-row
export function KpiRow({ items }) {
  return (
    <div className="kpis">
      {items.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="l">{k.label}</div>
          <div className="v">{k.value}</div>
          {k.sub && <div className="t">{k.sub}</div>}
        </div>
      ))}
    </div>
  );
}

// a labeled bar row (used for causes, levers, lever options)
export function BarRow({ name, p, dir, num }) {
  return (
    <div className="lrow">
      <div className="name">{name}</div>
      <div className={`bar ${dir || ""}`}><span style={{ width: Math.min(100, Math.round((p ?? 0) * 100)) + "%" }} /></div>
      <div className={`num ${dir || ""}`}>{num}</div>
    </div>
  );
}

// chart → funnel: the staged bars + step conversion with the leak flagged
export function FunnelChart({ stages, leak }) {
  const top = stages[0]?.count || 1;
  return (
    <div>
      {stages.map((s, i) => (
        <div key={s.key}>
          {i > 0 && (
            <div className={"conv" + (leak && leak.into === s.label ? " leak" : "")}>
              ↓ {pct(s.conversion_from_prev)} continue
              {leak && leak.into === s.label && <span className="tag">biggest drop</span>}
            </div>
          )}
          <div className="stage">
            <div className="top">
              <span className="nm">{s.label}</span>
              <span className="ct">{s.count.toLocaleString()} · {pct(s.rate_of_top)}</span>
            </div>
            <div className="track" style={{ width: Math.max(3, Math.round((s.count / top) * 100)) + "%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// chart → win-rate by quarter, a small SVG bar chart with a target line. The
// latest quarter is highlighted; the dashed line is the target win rate.
export function QuarterBars({ series, target = 0.28 }) {
  const W = 460, H = 210, padL = 26, padR = 10, base = 180, topY = 20;
  const scale = Math.max(0.35, target * 1.1, ...series.map((s) => s.win_rate)) * 1.08;
  const n = Math.max(1, series.length);
  const slot = (W - padL - padR) / n;
  const bw = Math.min(46, slot * 0.6);
  const y = (r) => base - (r / scale) * (base - topY);
  const grid = [0, scale / 2, scale];
  return (
    <div>
      <div className="cx-legend">
        <span className="lg"><span className="sw" style={{ background: "#5D50FF" }} />win rate</span>
        <span className="lg"><span className="sw" style={{ background: "#0fa39b" }} />target {pct(target)}</span>
      </div>
      <svg className="qbar-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {grid.map((v, i) => (
          <line key={i} x1={padL} y1={y(v)} x2={W - padR} y2={y(v)} stroke="#e6e8f2" strokeWidth="1" />
        ))}
        {series.map((s, i) => {
          const x = padL + i * slot + (slot - bw) / 2;
          const by = y(s.win_rate);
          return (
            <g key={s.label}>
              <rect x={x} y={by} width={bw} height={Math.max(0, base - by)} rx="3"
                    fill={i === n - 1 ? "#7d5bf0" : "#5D50FF"} />
              <text x={x + bw / 2} y={198} textAnchor="middle" className="caxis" fill="#8d91ab">{s.label}</text>
            </g>
          );
        })}
        <line x1={padL} y1={y(target)} x2={W - padR} y2={y(target)}
              stroke="#0fa39b" strokeWidth="2" strokeDasharray="5 4" />
      </svg>
    </div>
  );
}

// the Aito "why" / cause list: rate-with vs rate-without, or lift factors
export function WhyList({ items }) {
  if (!items?.length) return <div className="empty">no strong driver at this slice size</div>;
  return (
    <div className="list">
      {items.map((c, i) => {
        if (c.lift != null) {
          const up = c.lift >= 1;
          return <BarRow key={i} name={c.label} p={Math.min(c.lift, 5) / 5} dir={up ? "up" : "down"} num={"×" + c.lift.toFixed(2)} />;
        }
        const up = c.rate_with >= c.rate_without;
        return (
          <div className="lrow" key={i}>
            <div className="name"><b>{c.field?.replace("contact_id.", "")}</b> = {String(c.value)}</div>
            <div className={"num " + (up ? "up" : "down")}>{pct(c.rate_with)}</div>
            <div className="num" style={{ color: "var(--ink-faint)" }}>vs {pct(c.rate_without)}</div>
          </div>
        );
      })}
    </div>
  );
}

// a slip-risk chip: Aito's P(this todo slips), colored by band, with the
// driving factor as a tooltip. Quiet when there's no history to learn from.
function SlipRisk({ sr }) {
  if (!sr) return <span className="slip-empty" />;  // keep the row's grid columns aligned
  const band = sr.p >= 0.5 ? "hi" : sr.p >= 0.25 ? "mid" : "lo";
  return (
    <span className={"slip " + band} title={sr.top_factor ? "driver: " + sr.top_factor : ""}>
      slip {Math.round(sr.p * 100)}%
    </span>
  );
}

// action-pipeline: todos ranked, with status chip, priority, and due/area
// Swipe-to-act (touch only, so it never fights desktop drag-reorder or clicks):
// drag a row right past the threshold to mark it done, left to archive. A short
// drag snaps back. Undo lives one level up (EditableTodos defers the write).
const SWIPE_TRIGGER = 80;   // px past which a release fires the action
const SWIPE_MAX = 150;      // px the row can travel

function useSwipe({ onDone, onArchive }) {
  const [dx, setDx] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const st = useRef(null);          // {x, y, dir, moved, dx} — dx here is the
                                    // source of truth on release (state can lag)
  const suppress = useRef(false);   // swallow the click that may follow a swipe
  const enabled = !!(onDone || onArchive);

  // Touch events (not pointer): they fire only on touch, so a desktop mouse
  // keeps click and drag-reorder untouched with no pointerType check needed.
  const start = (e) => {
    const p = e.touches?.[0]; if (!enabled || !p) return;
    suppress.current = false;
    st.current = { x: p.clientX, y: p.clientY, dir: null, moved: false, dx: 0 };
    setSwiping(true);
  };
  const move = (e) => {
    const s = st.current, p = e.touches?.[0]; if (!s || !p) return;
    const dX = p.clientX - s.x, dY = p.clientY - s.y;
    if (!s.dir) {
      if (Math.abs(dX) < 8 && Math.abs(dY) < 8) return;
      s.dir = Math.abs(dX) > Math.abs(dY) ? "h" : "v";
    }
    if (s.dir !== "h") return;      // vertical intent → let the list scroll
    s.moved = true;
    let d = dX;
    if (d > 0 && !onDone) d = 0;    // only offer the directions that are wired
    if (d < 0 && !onArchive) d = 0;
    s.dx = Math.max(-SWIPE_MAX, Math.min(SWIPE_MAX, d));
    e.preventDefault?.();
    setDx(s.dx);
  };
  const end = () => {
    const s = st.current; st.current = null; setSwiping(false);
    if (s?.moved) suppress.current = true;
    const travel = s ? s.dx : 0;
    if (travel >= SWIPE_TRIGGER && onDone) onDone();
    else if (travel <= -SWIPE_TRIGGER && onArchive) onArchive();
    setDx(0);
  };
  return {
    dx, swiping, armed: dx >= SWIPE_TRIGGER ? "done" : dx <= -SWIPE_TRIGGER ? "arch" : "",
    tookClick: () => { const s = suppress.current; suppress.current = false; return s; },
    handlers: enabled
      ? { onTouchStart: start, onTouchMove: move, onTouchEnd: end, onTouchCancel: end }
      : {},
  };
}

// one action row, shared by the pipeline and calendar lenses. When onEdit is
// given, the whole row is a tap target that opens the editor (a thumb-sized
// hit area on mobile, not just the little pencil) and shows a pencil
// affordance. The inline buttons stopPropagation so ✓/✎ still do their own job.
// onDone/onArchive also enable swipe-right/left on touch.
export function ActionRow(props) {
  // A public demo refuses every write, so a row there carries none of the
  // controls that make one: no done box, no swipe, no edit pencil or row tap,
  // no assignee picker, no drag (docs/33). Each control only renders when its
  // handler is given, so withholding the handlers is the whole change.
  const ro = publicDemo();
  const { t, showArea, showDue } = props;
  const onEdit = ro ? undefined : props.onEdit;
  const onDone = ro ? undefined : props.onDone;
  const onArchive = ro ? undefined : props.onArchive;
  const drag = ro ? undefined : props.drag;
  const renderAssignee = ro ? undefined : props.renderAssignee;
  const stop = (fn) => (e) => { e.stopPropagation(); fn(); };
  const sw = useSwipe({ onDone: onDone && (() => onDone(t)),
                        onArchive: onArchive && (() => onArchive(t)) });
  const onRowClick = onEdit ? () => { if (!sw.tookClick()) onEdit(t); } : undefined;
  return (
    <div className="swrap">
      {(onDone || onArchive) && (
        <div className={"swipe-bg" + (sw.armed ? " armed-" + sw.armed : "")}>
          <span className="swipe-hint done">✓ done</span>
          <span className="swipe-hint arch">archive</span>
        </div>
      )}
      <div className={"arow p" + t.priority + (drag?.draggable ? " draggable" : "") + (onEdit ? " editable" : "")}
           onClick={onRowClick}
           style={{ transform: sw.dx ? `translateX(${sw.dx}px)` : undefined,
                    transition: sw.swiping ? "none" : undefined }}
           {...sw.handlers}
           draggable={drag?.draggable} onDragStart={drag?.onDragStart}
           onDragOver={drag?.onDragOver} onDrop={drag?.onDrop} onDragEnd={drag?.onDragEnd}>
        {onDone && <button className="done-box" title="mark done" onClick={stop(() => onDone(t))}>✓</button>}
        <div className="rk">{t.priority}</div>
        <div className="amid">
          <div className="att">
            {t.action_type && t.action_type !== "none" && <span className="atype">{t.action_type}</span>}
            {t.title}{t.company && <span className="co"> · {t.company}</span>}
            {onEdit && <button className="edit-pen" title="edit" onClick={stop(() => onEdit(t))}>✎</button>}
          </div>
          {t.detail && (
            <div className="adet" title="open to read/edit the full detail"
                 onClick={onEdit ? stop(() => onEdit(t)) : undefined}>{t.detail}</div>
          )}
          <div className="amm">
            {showArea && <span className="area">{t.area}</span>}
            {t.role && <span className="lane">⚙ {t.role}{t.owner ? " · " + t.owner : ""}</span>}
            {t.slot && <span className="slot">{t.slot}</span>}
            {showDue && t.due_date && <span>{t.overdue ? "overdue " : ""}due {t.due_date}{t.window ? " · " + t.window : ""}</span>}
            {!showDue && t.window && <span>{t.window}</span>}
            {t.prep_status !== "n_a" && <span> · {t.prep_status.replace(/_/g, " ")}</span>}
            {t.stakeholder && <span> · {t.stakeholder}</span>}
            {t.linked_type === "deal" && <span className="dealtag">→ deal</span>}
          </div>
        </div>
        <div className="ameta">
          <SlipRisk sr={t.slip_risk} />
          {renderAssignee && renderAssignee(t)}
          <div className={"st " + t.status}>{t.status}</div>
        </div>
      </div>
    </div>
  );
}

// the pipeline lens, drag-reorderable when onReorder is given. Reorders the
// local list optimistically, then persists the new order in one write.
export function ActionPipeline({ todos, showArea, onEdit, onDone, onArchive, onReorder, renderAssignee }) {
  const [order, setOrder] = useState(todos);
  const from = useRef(null);
  useEffect(() => setOrder(todos), [todos]);  // re-sync when the data refreshes
  if (!order?.length) return <div className="empty">nothing open here</div>;
  const handleDrop = (to) => {
    const i = from.current;
    from.current = null;
    if (i == null || i === to) return;
    const next = [...order];
    const [moved] = next.splice(i, 1);
    next.splice(to, 0, moved);
    setOrder(next);
    onReorder && onReorder(next.map((t) => t.todo_id));
  };
  return (
    <div className="actions">
      {order.map((t, i) => (
        <ActionRow key={t.todo_id} t={t} showArea={showArea} showDue onEdit={onEdit}
                   onDone={onDone} onArchive={onArchive} renderAssignee={renderAssignee}
                   drag={onReorder ? {
                     draggable: true,
                     onDragStart: () => { from.current = i; },
                     onDragOver: (e) => e.preventDefault(),
                     onDrop: () => handleDrop(i),
                   } : null} />
      ))}
    </div>
  );
}

// action-calendar: the same todos grouped under their due date
export function ActionCalendar({ todos, onEdit, onDone, onArchive, renderAssignee }) {
  if (!todos?.length) return <div className="empty">nothing scheduled here</div>;
  const byDay = {};
  todos.forEach((t) => { (byDay[t.due_date] = byDay[t.due_date] || []).push(t); });
  return (
    <div className="cal">
      {Object.keys(byDay).sort().map((day) => (
        <div className="calday" key={day}>
          <div className={"daylabel" + (byDay[day][0].overdue ? " over" : "")}>
            {day}{byDay[day][0].overdue ? " · overdue" : ""}
          </div>
          {byDay[day].map((t) => (
            <ActionRow key={t.todo_id} t={t} onEdit={onEdit} onDone={onDone}
                       onArchive={onArchive} renderAssignee={renderAssignee} />
          ))}
        </div>
      ))}
    </div>
  );
}

// a week-grid calendar: the scheduled todos laid out Mon–Sun by day, ordered
// by time slot within a day. Today is highlighted; prev/next walks weeks. A
// chip click opens the editor. Todos outside the visible week stay in the list
// below.
const _WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
function _ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function WeekCalendar({ todos, events, onEdit }) {
  const [offset, setOffset] = useState(0);
  const base = clockNow();
  base.setHours(0, 0, 0, 0);
  base.setDate(base.getDate() - ((base.getDay() + 6) % 7) + offset * 7);  // Monday + offset weeks
  const days = [...Array(7)].map((_, i) => { const d = new Date(base); d.setDate(base.getDate() + i); return d; });
  const today = _ymd(clockNow());
  const byDay = {};
  (todos || []).forEach((t) => { if (t.due_date) (byDay[t.due_date] = byDay[t.due_date] || []).push(t); });
  Object.values(byDay).forEach((l) => l.sort((a, b) => (a.slot || "99:99").localeCompare(b.slot || "99:99")));
  const evByDay = {};
  (events || []).forEach((e) => { if (e.starts) (evByDay[e.starts] = evByDay[e.starts] || []).push(e); });
  return (
    <div className="weekcal">
      <div className="wc-head">
        <button onClick={() => setOffset((o) => o - 1)} title="previous week">‹</button>
        <span className="wc-range">{_ymd(days[0])} – {_ymd(days[6])}</span>
        <button onClick={() => setOffset((o) => o + 1)} title="next week">›</button>
        {offset !== 0 && <button className="wc-today" onClick={() => setOffset(0)}>today</button>}
      </div>
      <div className="wc-grid">
        {days.map((d) => {
          const ds = _ymd(d);
          const items = byDay[ds] || [];
          return (
            <div key={ds} className={"wc-day" + (ds === today ? " is-today" : "")}>
              <div className="wc-daylabel">{_WD[(d.getDay() + 6) % 7]} <b>{d.getDate()}</b></div>
              {(evByDay[ds] || []).map((e) => (
                <div key={e.event_id} className={"wc-ev " + e.status} title={`${e.name} · ${e.status}`}>
                  <span className="wc-evdot">◆</span><span className="wc-t">{e.name}</span>
                </div>
              ))}
              {items.map((t) => (
                <div key={t.todo_id} className={"wc-item p" + t.priority}
                     onClick={onEdit ? () => onEdit(t) : undefined} title={t.title}>
                  {t.slot && <span className="wc-time">{t.slot}</span>}
                  <span className="wc-t">{t.title}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// a lever (recommend) block: best option, flagged when it differs from current
export function Levers({ levers }) {
  if (!levers?.length) return <div className="empty">no levers</div>;
  return levers.map((lv) => (
    <div className={"lever" + (lv.actionable ? " act" : "")} key={lv.field}>
      <div className="fn">{lv.field.replace(/_/g, " ")}</div>
      <div className="sw">
        {lv.actionable
          ? <>▸ switch to <b>{lv.best}</b> (from {lv.current})</>
          : <>keep <b>{lv.best ?? lv.current}</b></>}
      </div>
    </div>
  ));
}
