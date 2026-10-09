// What the server said about this session, for components that must behave
// differently without prop-drilling it: set once from /api/me (see App).
//
// publicDemo: the instance is a read-only demo for anonymous visitors
// (docs/33). The server refuses every write with a 403 either way; this is so
// the UI does not OFFER controls that can only fail, nor views a guest cannot
// read (the raw-table sheets are operator-only by design — they expose whole
// tables — and a demo pointed at the wrong database must not publish them).
let _publicDemo = false;

export function setPublicDemo(v) { _publicDemo = !!v; }
export function publicDemo() { return _publicDemo; }
