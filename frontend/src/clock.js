// The client half of src/company_ai/clock.py.
//
// When the instance declares a reckoning date, the browser has to use it too:
// otherwise the week strip sits on the real week (empty) while the list under
// it shows work from the dataset's week, which reads as a broken view rather
// than a sample one. Set once from /api/me; null means the real clock.
let _asOf = null;

export function setReckoning(iso) { _asOf = iso || null; }
export function reckoning() { return _asOf; }

/** The date the UI should treat as "now". */
export function now() {
  return _asOf ? new Date(_asOf + "T00:00:00") : new Date();
}

/** `now()` as YYYY-MM-DD, the form the API speaks. */
export function todayIso() {
  const d = now();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
