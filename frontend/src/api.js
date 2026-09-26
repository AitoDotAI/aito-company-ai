// Thin fetch helpers over the FastAPI contract (the same data the agent
// reaches via MCP). Every call returns the backend's .derived payload, or
// throws with the {error} the backend surfaced.

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== "")
  ).toString();
  const res = await fetch(`/api${path}${qs ? "?" + qs : ""}`);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function send(method, path, body, signal) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,   // optional AbortSignal — lets the caller cancel the request
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
const post = (path, body, signal) => send("POST", path, body, signal);
const patch = (path, body) => send("PATCH", path, body);
const put = (path, body) => send("PUT", path, body);
const del = (path) => send("DELETE", path);

export const api = {
  todos: (lens, area) => get("/todos", { lens, area }),
  todoOptions: () => get("/todo-options"),
  createTodo: (fields) => post("/todos", fields),
  updateTodo: (id, changes) => patch(`/todos/${id}`, changes),
  completeTodo: (id, body) => post(`/todos/${id}/complete`, body || {}),
  archiveTodo: (id) => post(`/todos/${id}/archive`, {}),
  reorderTodos: (ids) => post("/todos/reorder", { ids }),
  classifyTodo: (title, given) => post("/todos/classify", { title, given: given || {} }),
  deals: () => get("/deals"),
  whoToReach: () => get("/who-to-reach"),
  salesTrend: () => get("/sales-trend"),
  pwin: (stage, blocker, champion_present) => get("/pwin", { stage, blocker, champion_present }),
  graph: () => get("/graph"),
  companies: () => get("/companies"),
  companyDetail: (id) => get(`/companies/${id}`),
  createCompany: (name) => post("/companies", { name }),
  createContact: (fields) => post("/contacts", fields),
  quickFind: (q) => get("/quickfind", { q }),
  search: (q, kind) => get("/search", kind ? { q, kind } : { q }),
  searchClick: (context_id, item_id) => post("/search/click", { context_id, item_id }),
  reindexSearch: () => post("/search/reindex", {}),
  decisions: () => get("/decisions"),
  tables: () => get("/tables"),
  table: (name, where) => get("/table", where ? { name, where: JSON.stringify(where) } : { name }),
  experiments: () => get("/experiments"),
  events: () => get("/events"),
  createEvent: (fields) => post("/events", fields),
  decideEvent: (id, body) => post(`/events/${id}/decide`, body),
  routines: () => get("/routines"),
  createRoutine: (fields) => post("/routines", fields),
  updateRoutine: (id, changes) => patch(`/routines/${id}`, changes),
  tickRoutine: (id) => post(`/routines/${id}/tick`, {}),
  prepareRoutine: (id) => post(`/routines/${id}/prepare`, {}),
  runRoutine: (id) => post(`/routines/${id}/run`, {}),
  me: () => get("/me"),
  users: () => get("/users"),
  createUser: (fields) => post("/users", fields),
  updateUser: (id, changes) => patch(`/users/${id}`, changes),
  assign: (entity, entityId, userId) => post("/assignments", { entity, entity_id: entityId, user_id: userId }),
  assignments: (entity) => get("/assignments", entity ? { entity } : undefined),
  myWork: () => get("/my-work"),
  tokens: () => get("/tokens"),
  createToken: (label) => post("/tokens", { label }),
  revokeToken: (id) => del(`/tokens/${id}`),
  changelog: (entity) => get("/changelog", entity ? { entity } : {}),
  // assistant conversations, stored server-side (durable across devices)
  chatsList: () => get("/chats"),
  chatSave: (id, body) => put(`/chats/${id}`, body),
  chatRemove: (id) => del(`/chats/${id}`),
  documents: (params) => get("/documents", params),
  createDocument: (fields) => post("/documents", fields),
  updateDocument: (id, changes) => patch(`/documents/${id}`, changes),
  classifyDocument: (title, given) => post("/documents/classify", { title, given: given || {} }),
  documentContext: (title, company) => post("/documents/context", { title, company: company || null }),
  deleteDocument: (id) => del(`/documents/${id}`),
  dimensions: () => get("/dimensions"),
  segment360: (slice) => get("/360", slice),
  funnelCatalog: () => get("/funnels"),
  funnel: (name, slice) => get("/funnel", { name, ...slice }),
  scoreOptions: () => get("/score-options"),
  score: (platform, features) => get("/score", { platform, ...features }),
  createMaterial: (fields) => post("/materials", fields),
  createChannel: (fields) => post("/channels", fields),
  createPost: (fields) => post("/posts", fields),
  logPostResult: (id, body) => post(`/posts/${id}/result`, body),
  // the right-side assistant: send the conversation, get a grounded reply +
  // the trace of Aito-backed tools the loop ran.
  assistant: (messages, signal) => post("/assistant/chat", { messages }, signal),
};

export const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
