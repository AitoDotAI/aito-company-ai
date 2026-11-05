// Web: aito.ai visits (docs/35), laid out like the e-commerce Analytics page:
// KPIs and filters on the left, the trend and Aito's insights on the right,
// the sessions at the bottom. Totals are counts; the drivers are Aito's
// _relate and the next pages its _predict, each shown with its evidence.
import React, { useState, useEffect, useRef } from "react";
import { todayIso } from "./clock.js";
import { api } from "./api.js";
import { Loading, ErrorBox } from "./primitives.jsx";

const KPIS = [
  { key: "sessions", label: "Sessions", value: (t) => t.sessions, day: (d) => d.sessions,
    fmt: (v) => String(v) },
  { key: "onward", label: "Onward click", value: (t) => (t.sessions ? t.onward_clicks / t.sessions : 0),
    day: (d) => (d.sessions ? d.onward_clicks / d.sessions : 0), fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "cta", label: "Sign-up CTA", value: (t) => (t.sessions ? t.signup_ctas / t.sessions : 0),
    day: (d) => (d.sessions ? d.signup_ctas / d.sessions : 0), fmt: (v) => `${Math.round(v * 100)}%` },
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

export function WebView() {
  const [period, setPeriod] = useState("30");
  const [f, setF] = useState({ source: "", path: "", campaign: "", device: "" });
  const [kpiKey, setKpiKey] = useState("sessions");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const latest = useRef(0);

  useEffect(() => {
    const call = ++latest.current;                    // a slow older answer never wins
    Promise.resolve(api.web({ since: daysBack(Number(period)), until: todayIso(), ...f,
                              limit: PAGE, offset }))
      .then((d) => { if (call === latest.current && d) { setData(d); setErr(null); } })
      .catch((e) => { if (call === latest.current) setErr(String(e.message || e)); });
  }, [period, f.source, f.path, f.campaign, f.device, offset]);

  const pick = (k) => (ev) => { setOffset(0); setF((s) => ({ ...s, [k]: ev.target.value })); };
  const kpi = KPIS.find((k) => k.key === kpiKey);
  if (err) return <ErrorBox msg={err} />;
  if (!data) return <Loading label="Reading the visits…" />;
  const t = data.totals;
  const rels = (data.drivers && data.drivers.relations) || [];

  return (
    <div className="web">
      <div className="web-grid">
        <aside className="web-left">
          <div className="web-kpis" data-testid="web-kpis">
            {KPIS.map((k) => (
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
          <h3>What goes with an onward click <span className="muted">· Aito _relate</span></h3>
          <div className="web-drivers" data-testid="web-drivers">
            {rels.length ? rels.map((r, i) => (
              <div key={i} className="web-driver">
                <span className="web-driver-k">{`${r.field} = ${r.value}`}</span>
                {r.thin
                  ? <span className="web-thin">thin · {r.rows_with} sessions, no claim</span>
                  : <span className="web-lift">
                      {r.lift.toFixed(1)}× · {Math.round(r.rate_with * 100)}% vs{" "}
                      {Math.round(r.rate_without * 100)}% · {r.rows_with} sessions
                    </span>}
              </div>
            )) : <div className="muted">Not enough sessions with an onward click to relate.</div>}
          </div>
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
