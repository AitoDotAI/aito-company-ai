// The tech tree (docs/45): product and research lines as a map. Eras run left
// to right as columns, branches run top to bottom as bands, prerequisites are
// curves. Hover a node to light its prerequisite chain; click it for the
// panel; the legend filters by status. Positions come from each node's era
// and row, so edges are computed, never measured from the DOM.
import React, { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const COLW = 212, ROWH = 76, LEFT = 40, TOP = 62, NODEW = 176, NODEH = 60;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"];

function ancestors(byId, id, acc = new Set()) {
  for (const r of byId[id]?.requires || []) {
    if (!acc.has(r)) { acc.add(r); ancestors(byId, r, acc); }
  }
  return acc;
}

const pos = (n) => ({ x: LEFT + n.era * COLW, y: TOP + n.row * ROWH });

export function TechTree() {
  const [tree, setTree] = useState(null);
  const [error, setError] = useState(null);
  const [sel, setSel] = useState(null);
  const [hover, setHover] = useState(null);
  const [hidden, setHidden] = useState(() => new Set());

  useEffect(() => {
    api.techTree().then(setTree).catch((e) => setError(e.message));
  }, []);

  const byId = useMemo(() => Object.fromEntries((tree?.nodes || []).map((n) => [n.node_id, n])), [tree]);
  if (error) return <div className="tt-error">Could not read the tech tree: {error}</div>;
  if (!tree) return <div className="tt-loading">Reading the tech tree…</div>;

  const nodes = tree.nodes;
  const focus = hover || sel;
  const chain = focus ? ancestors(byId, focus) : new Set();
  const rows = Math.max(0, ...nodes.map((n) => n.row)) + 1;
  const width = LEFT + COLW * tree.eras.length + 8;
  const height = TOP + ROWH * rows + 12;
  const bands = tree.branches.map((b) => {
    const rs = nodes.filter((n) => n.branch === b).map((n) => n.row);
    return { name: b, r0: Math.min(...rs), r1: Math.max(...rs) };
  });
  const edges = nodes.flatMap((n) => n.requires.map((r) => {
    const a = pos(byId[r]), z = pos(n);
    const x1 = a.x + NODEW, y1 = a.y + NODEH / 2, x2 = z.x, y2 = z.y + NODEH / 2;
    const dx = Math.max(30, (x2 - x1) / 2);
    const hot = !!focus && (n.node_id === focus || (chain.has(n.node_id) && chain.has(r)));
    return { from: r, to: n.node_id, hot,
             d: `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}` };
  }));
  const toggle = (k) => setHidden((h) => { const s = new Set(h); s.has(k) ? s.delete(k) : s.add(k); return s; });
  const go = (id) => {
    setSel(id);
    document.getElementById(`tt-${id}`)?.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "smooth" });
  };
  const s = sel && byId[sel];

  return (
    <div className="tt">
      <div className="tt-legend" role="group" aria-label="Filter by status">
        {Object.entries(tree.statuses).map(([k, label]) => (
          <button key={k} type="button" aria-pressed={!hidden.has(k)} onClick={() => toggle(k)}>
            <span className={`tt-dot ${k}`} />{label} <span className="tt-count">{nodes.filter((n) => n.status === k).length}</span>
          </button>
        ))}
      </div>
      <div className="tt-layout">
        <div className="tt-mapwrap">
          <div className="tt-map" style={{ width, height }}>
            {bands.map((b, i) => (
              <React.Fragment key={b.name}>
                <div className={`tt-band${i % 2 ? " alt" : ""}`}
                     style={{ top: TOP + b.r0 * ROWH - 8, height: (b.r1 - b.r0 + 1) * ROWH }} />
                <div className="tt-bandlabel" style={{ top: TOP + b.r0 * ROWH, height: (b.r1 - b.r0 + 1) * ROWH - 14 }}>{b.name}</div>
              </React.Fragment>
            ))}
            {tree.eras.map((e, i) => (
              <div key={e} className="tt-era" style={{ left: LEFT + i * COLW, width: NODEW }}><b>{ROMAN[i]}</b>{e}</div>
            ))}
            <svg className="tt-edges" width={width} height={height} aria-hidden="true">
              {edges.map((e) => <path key={`${e.from}-${e.to}`} d={e.d} data-from={e.from} data-to={e.to} className={e.hot ? "hot" : undefined} />)}
            </svg>
            {nodes.map((n) => {
              const { x, y } = pos(n);
              const cls = ["tt-node", n.status, hidden.has(n.status) && "dim", chain.has(n.node_id) && "chain",
                           n.node_id === sel && "sel"].filter(Boolean).join(" ");
              return (
                <button key={n.node_id} id={`tt-${n.node_id}`} type="button" className={cls}
                        style={{ left: x, top: y, width: NODEW, height: NODEH }}
                        aria-label={`${n.title}, ${tree.statuses[n.status]}`}
                        onClick={() => setSel(n.node_id)}
                        onMouseEnter={() => setHover(n.node_id)} onMouseLeave={() => setHover(null)}
                        onFocus={() => setHover(n.node_id)} onBlur={() => setHover(null)}>
                  <span className="tt-ic" /><span className="tt-t">{n.title}</span>
                  {n.metric && <span className="tt-m">{n.metric}</span>}
                </button>
              );
            })}
          </div>
        </div>
        <aside className="tt-panel" data-testid="tt-panel" aria-live="polite">
          {!s ? <p className="tt-hint">Click a node for its state, next step and article. Hover one to light what it requires.</p> : (<>
            <span className="tt-chip"><span className={`tt-dot ${s.status}`} />{tree.statuses[s.status]}</span>
            <h2>{s.title}</h2>
            <div className="tt-where">{s.branch} · Era {ROMAN[s.era]}, {tree.eras[s.era]} · updated {s.updated_on}</div>
            <dl>
              <dt>What</dt><dd>{s.what}</dd>
              <dt>State</dt><dd>{s.state}</dd>
              <dt>Next</dt><dd>{s.next}</dd>
              <dt>Owner</dt><dd>{s.owner || "—"}</dd>
              <dt>Requires</dt><dd className="tt-reqs">{s.requires.length ? s.requires.map((r) =>
                <button key={r} type="button" onClick={() => go(r)}>{byId[r].title}</button>) : "None"}</dd>
              <dt>Unlocks</dt><dd className="tt-reqs">{(() => {
                const un = nodes.filter((x) => x.requires.includes(s.node_id));
                return un.length ? un.map((x) => <button key={x.node_id} type="button" onClick={() => go(x.node_id)}>{x.title}</button>) : "None";
              })()}</dd>
              <dt>Article</dt><dd>{s.doc_id ? <a href={`#/documents/${s.doc_id}`}>Open the article →</a> : "None yet"}</dd>
            </dl>
          </>)}
        </aside>
      </div>
    </div>
  );
}
