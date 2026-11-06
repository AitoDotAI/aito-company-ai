// Web: aito.ai visits (docs/35, docs/36), laid out like the e-commerce
// Analytics page: KPIs and filters on the left, the trend and Aito's insights
// on the right, the sessions at the bottom. Totals are counts; the drivers,
// other KPIs, other events and acquisition are Aito's _relate and the next
// pages its _predict, each shown with its evidence. Journeys are individual
// browsing histories: internal only, never on a public demo.
import React, { useState, useEffect, useRef } from "react";
import { todayIso } from "./clock.js";
import { api } from "./api.js";
import { publicDemo } from "./session.js";
import { Loading, ErrorBox } from "./primitives.jsx";

const pct = (v) => `${Math.round(v * 100)}%`;
const rate = (n, d) => (d ? n / d : 0);

// the visit-level KPIs (docs/35)
const VISIT_KPIS = [
  { key: "sessions", label: "Sessions", value: (t) => t.sessions, day: (d) => d.sessions,
    fmt: (v) => String(v) },
  { key: "onward", label: "Onward click", value: (t) => rate(t.onward_clicks, t.sessions),
    day: (d) => rate(d.onward_clicks, d.sessions), fmt: pct },
  { key: "cta", label: "Sign-up CTA", value: (t) => rate(t.signup_ctas, t.sessions),
    day: (d) => rate(d.signup_ctas, d.sessions), fmt: pct },
];
// the preselected KPIs (docs/36), in funnel order
const KPI_LABELS = [
  ["pricing_page", "Pricing page"], ["contact_page", "Contact page"], ["login_page", "Login page"],
  ["signup", "Sign-up"], ["sandbox", "Sandbox"], ["data_loaded", "Data loaded"],
  ["first_query", "First query"], ["api_keys", "API keys"],
];
const PERIODS = [["7", "7 days"], ["30", "30 days"], ["90", "90 days"]];
const PAGE = 25;
const FILTERS = [["source", "Source", "source"], ["path", "Landing page", "landing_path"],
                 ["campaign", "Campaign", "utm_campaign"], ["device", "Device", "device_class"]];
const COLUMNS = ["Day", "Hour", "Landing", "Next", "Source", "Referrer", "Campaign", "Device",
                 "Country", "Views", "Onward", "CTA"];

function daysBack(n) {
  const d = new Date(todayIso() + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - (n - 1));
  return d.toISOString().slice(0, 10);
}

function Trend({ days, kpi }) {
  const W = 560, H = 150, P = 24;
  if (!days.length) return <div className="muted">No sessions in this window.</div>;
  const vals = days.map(kpi.day);
  const max = Math.max(...vals, kpi.key === "sessions" ? 1 : 0.01);
  const x = (i) => P + (days.length === 1 ? (W - 2 * P) / 2 : (i * (W - 2 * P)) / (days.length - 1));
  const y = (v) => H - P - (v / max) * (H - 2 * P);
  const line = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className="web-trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${kpi.label} per day`}>
      <line x1={P} y1={H - P} x2={W - P} y2={H - P} className="web-axis" />
      <path d={line} className="web-line" />
      {vals.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={2.5} className="web-pt">
          <title>{`${days[i].day}: ${kpi.fmt(v)}`}</title>
        </circle>
      ))}
      <text x={P} y={H - 6} className="web-tick">{days[0].day}</text>
      <text x={W - P} y={H - 6} textAnchor="end" className="web-tick">{days[days.length - 1].day}</text>
      <text x={P} y={P - 8} className="web-tick">{kpi.fmt(max)}</text>
    </svg>
  );
}

// one Aito relation per row: the lift with its counts, or "thin" without a claim
function Relations({ rels, empty, testid, unit = "sessions" }) {
  if (!rels || !rels.length) return <div className="muted">{empty}</div>;
  return (
    <div className="web-drivers" data-testid={testid}>
      {rels.map((r, i) => (
        <div key={i} className="web-driver">
          <span className="web-driver-k">{`${r.field} = ${r.value}`}</span>
          {r.thin
            ? <span className="web-thin">thin · {r.rows_with} {unit}, no claim</span>
            : <span className="web-lift">
                {r.lift.toFixed(1)}× · {pct(r.rate_with)} vs {pct(r.rate_without)} · {r.rows_with} {unit}
              </span>}
        </div>
      ))}
    </div>
  );
}

function Paths({ query }) {
  const [paths, setPaths] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let live = true;
    Promise.resolve(api.webPaths(query))
      .then((d) => { if (live && d) setPaths(d); })
      .catch((e) => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, [query.kpi, query.since, query.until]);
  if (err) return <ErrorBox msg={err} />;
  if (!paths) return <Loading label="Walking the steps…" />;
  if (paths.note) return <div className="muted">{paths.note}</div>;
  return (
    <div className="web-paths">
      <h4>Top paths into it <span className="muted">· Aito $patterns</span></h4>
      {paths.top_paths.length ? paths.top_paths.map((p, i) => (
        <div key={i} className="web-driver">
          <span className="web-driver-k">{p.path.join(" → ")}</span>
          {p.thin ? <span className="web-thin">thin · {p.visits} visits, no claim</span>
                  : <span className="web-lift">{p.visits} visits · {p.lift.toFixed(1)}×</span>}
        </div>
      )) : <div className="muted">No path repeats often enough yet.</div>}
      <h4>Pages after which it more often follows</h4>
      <Relations rels={(paths.raises_later && paths.raises_later.relations) || []} unit="steps"
                 empty="Nothing to relate yet." />
      <h4>Where visits that never reach it end</h4>
      <Relations rels={(paths.drop_off && paths.drop_off.relations) || []} unit="steps"
                 empty="Nothing to relate yet." />
    </div>
  );
}

function KpiInsights({ answer, hideJourneys, pathsQuery }) {
  const tabs = [["drivers", "Drivers"], ["other_kpis", "Other KPIs"], ["other_events", "Other events"],
                ["acquisition", "Acquisition"], ["paths", "Paths"],
                ...(hideJourneys ? [] : [["journeys", "Journeys"]])];
  const [tab, setTab] = useState("drivers");
  const rels = (part) => (answer[part] && answer[part].relations) || [];
  return (
    <>
      <div className="muted web-foot">
        {answer.with_target} of {answer.sessions} sessions reached it.
        {answer.dropped_as_linked && answer.dropped_as_linked.length > 0 && (
          <> Left out as steps of the same console funnel:{" "}
            {answer.dropped_as_linked.map((f) => f.replace(/^kpi_/, "")).join(", ")}.</>
        )}
      </div>
      <div className="web-tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""}
                  onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {tab === "drivers" && <Relations rels={rels("drivers")} empty="Nothing to relate yet." />}
      {tab === "other_kpis" && <Relations rels={rels("other_kpis")} empty="No other KPI goes with it yet." />}
      {tab === "other_events" && <Relations rels={rels("other_events")} empty="No other event goes with it yet." />}
      {tab === "acquisition" && (answer.acquisition
        ? <Relations rels={rels("acquisition")} unit="visitors" empty="No first touch goes with it yet." />
        : <div className="muted">No visitor has reached it yet.</div>)}
      {tab === "paths" && pathsQuery && <Paths query={pathsQuery} />}
      {tab === "journeys" && !hideJourneys && (
        <div className="web-journeys">
          {(answer.journeys || []).map((j) => (
            <div key={j.label} className="web-journey">
              <b>{j.label}</b>
              {j.sessions.map((s, i) => (
                <div key={i} className="muted">{s.day} {String(s.hour).padStart(2, "0")}h · {s.landing_path}
                  {" · "}{s.source} · <span className="web-driver-k">{s.events}</span></div>
              ))}
            </div>
          ))}
          {!(answer.journeys || []).length && <div className="muted">No journey reached it yet.</div>}
        </div>
      )}
      <div className="muted web-foot">
        Thin = fewer than {answer.thin_below} carry the value: listed, but no lift is claimed.
      </div>
    </>
  );
}

export function WebView() {
  const [period, setPeriod] = useState("30");
  const [f, setF] = useState({ source: "", path: "", campaign: "", device: "" });
  const [kpiKey, setKpiKey] = useState("sessions");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [err, setErr] = useState(null);
  const latest = useRef(0);
  const latestKpi = useRef(0);
  const since = daysBack(Number(period)), until = todayIso();
  const isKpi = kpiKey.startsWith("kpi:");

  useEffect(() => {
    const call = ++latest.current;                    // a slow older answer never wins
    Promise.resolve(api.web({ since, until, ...f, limit: PAGE, offset }))
      .then((d) => { if (call === latest.current && d) { setData(d); setErr(null); } })
      .catch((e) => { if (call === latest.current) setErr(String(e.message || e)); });
  }, [period, f.source, f.path, f.campaign, f.device, offset]);

  useEffect(() => {
    if (!isKpi) { setAnswer(null); return; }
    const call = ++latestKpi.current;
    setAnswer(null);
    Promise.resolve(api.webKpi({ kpi: kpiKey.slice(4), since, until, ...f }))
      .then((d) => { if (call === latestKpi.current && d) setAnswer(d); })
      .catch((e) => { if (call === latestKpi.current) setErr(String(e.message || e)); });
  }, [kpiKey, period, f.source, f.path, f.campaign, f.device]);

  const pick = (k) => (ev) => { setOffset(0); setF((s) => ({ ...s, [k]: ev.target.value })); };
  if (err) return <ErrorBox msg={err} />;
  if (!data) return <Loading label="Reading the visits…" />;
  const t = data.totals;
  const kpiList = [
    ...VISIT_KPIS,
    ...KPI_LABELS.map(([k, label]) => ({
      key: `kpi:${k}`, label, value: () => (data.kpis || {})[k] || 0,
      day: (d) => d[`kpi_${k}`] || 0, fmt: (v) => String(v),
    })),
  ];
  const kpi = kpiList.find((k) => k.key === kpiKey);
  const hideJourneys = publicDemo() || (answer && answer.journeys_hidden);

  return (
    <div className="web">
      <div className="web-grid">
        <aside className="web-left">
          <div className="web-kpis" data-testid="web-kpis">
            {kpiList.map((k) => (
              <button key={k.key} className={"web-kpi" + (k.key === kpiKey ? " on" : "")}
                      onClick={() => setKpiKey(k.key)}>
                <span className="web-kpi-l">{k.label}</span>
                <span className="web-kpi-v">{k.fmt(k.value(t))}</span>
              </button>
            ))}
          </div>
          <div className="muted web-bots">{t.bots} likely bot sessions left out</div>
          <div className="web-filters">
            <label>Period
              <select aria-label="Period" value={period}
                      onChange={(ev) => { setOffset(0); setPeriod(ev.target.value); }}>
                {PERIODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {FILTERS.map(([k, label, facet]) => (
              <label key={k}>{label}
                <select aria-label={label} value={f[k]} onChange={pick(k)}>
                  <option value="">all</option>
                  {(data.facets[facet] || []).map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </label>
            ))}
          </div>
        </aside>
        <section className="web-right">
          <h3>{kpi.label} per day</h3>
          <Trend days={data.days} kpi={kpi} />
          {isKpi ? (
            <>
              <h3>{kpi.label} <span className="muted">· Aito _relate</span></h3>
              {answer ? <KpiInsights key={kpiKey} answer={answer} hideJourneys={hideJourneys}
                                     pathsQuery={{ kpi: kpiKey.slice(4), since, until }} />
                      : <Loading label="Relating…" />}
            </>
          ) : (
            <>
              <h3>What goes with an onward click <span className="muted">· Aito _relate</span></h3>
              <Relations rels={(data.drivers && data.drivers.relations) || []} testid="web-drivers"
                         empty="Not enough sessions with an onward click to relate." />
              {data.thin_below != null && (
                <div className="muted web-foot">
                  Thin = fewer than {data.thin_below} sessions carry the value: listed, but no lift is claimed.
                </div>
              )}
              {data.next_paths && (
                <>
                  <h3>Next page from {data.filters.landing_path}{" "}
                    <span className="muted">· Aito _predict</span></h3>
                  <div className="web-next" data-testid="web-next">
                    {data.next_paths.hits.map((h) => (
                      <div key={String(h.value)} className="web-driver">
                        <span className="web-driver-k">{h.value == null ? "(left the site)" : h.value}</span>
                        <span className="web-lift">{Math.round(h.p * 100)}%</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </section>
      </div>
      <section className="web-table" data-testid="web-sessions">
        <div className="web-table-h">
          <h3>Sessions</h3>
          <span className="muted">
            {data.session_total
              ? `${offset + 1}–${offset + data.sessions.length} of ${data.session_total}` : "none"}
          </span>
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
          <button disabled={offset + PAGE >= data.session_total} onClick={() => setOffset(offset + PAGE)}>Next</button>
        </div>
        <div className="web-scroll">
          <table>
            <thead><tr>{COLUMNS.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {data.sessions.map((r, i) => (
                <tr key={i} className={r.likely_bot ? "bot" : ""}>
                  <td>{r.day}</td><td>{r.hour}</td><td>{r.landing_path}</td><td>{r.next_path || ""}</td>
                  <td>{r.source}</td><td>{r.referrer_domain || ""}</td><td>{r.utm_campaign || ""}</td>
                  <td>{r.device_class}</td><td>{r.country}</td><td>{r.views}</td>
                  <td>{r.onward_click ? "yes" : ""}</td><td>{r.signup_cta ? "yes" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
