"""The tech tree: product and research lines as nodes with prerequisites
(docs/45).

A node sits in a branch (a band of rows) and an era (a column, foundations to
in market), has a status, and names the nodes it requires. `tech_tree` reads
them all with `requires` parsed to a list; `upsert_tech_node` writes one node
by its id. Both hold the tree to its invariants (rule 3): every prerequisite
exists, there is no cycle, ids are [a-z0-9-], values are in the vocabulary,
no two nodes share a spot, and a document link names a real document. A
stored tree that breaks one raises with the node rather than drawing a wrong
map; a write that would break one is refused before anything is written.

Nothing here predicts: the tree is a record the lanes keep current, read and
drawn as it is.
"""

import re
from datetime import date

from . import changelog, schema
from .aito import AitoClient

TABLE = "tech_nodes"
ERAS = ["Foundations", "Proven", "Hardening", "Customer-ready", "In market"]
# status -> the label the view shows. "decision" waits on the operator.
STATUSES = {"done": "Researched", "active": "In progress", "open": "Ready to start",
            "decision": "Your decision", "locked": "Locked"}
ID = re.compile(r"[a-z0-9-]{1,40}")
FIELDS = [c for c in schema.TECH_NODES["columns"] if c != "node_id"]
REQUIRED = ("title", "branch", "era", "row", "status", "what", "state", "next")
OPTIONAL = ("metric", "owner", "requires", "doc_id", "recommendation", "reasons")
READ_LIMIT = 10_000


def _parse_requires(value, node: dict) -> list[str]:
    if value is None or value == "":
        return []
    ids = value.split() if isinstance(value, str) else list(value)
    for r in ids:
        assert isinstance(r, str) and ID.fullmatch(r), \
            f"tech node {node.get('node_id')!r}: requires id {r!r} is not [a-z0-9-]: {node}"
    assert len(ids) == len(set(ids)), f"tech node {node.get('node_id')!r}: a prerequisite twice: {node}"
    return ids


def parse_node(row: dict) -> dict:
    """One node, checked on its own: id, vocabulary, types. `requires` comes
    back as a list whether it arrived as a list or as the stored string."""
    node_id = row.get("node_id")
    assert isinstance(node_id, str) and ID.fullmatch(node_id), \
        f"tech node id {node_id!r} is not 1-40 of [a-z0-9-]: {row}"
    unknown = set(row) - set(FIELDS) - {"node_id"}
    assert not unknown, f"tech node {node_id!r}: unknown fields {sorted(unknown)}: {row}"
    for f in REQUIRED:
        assert row.get(f) not in (None, ""), f"tech node {node_id!r}: {f} is empty: {row}"
    assert row["status"] in STATUSES, \
        f"tech node {node_id!r}: unknown status {row['status']!r} (one of {sorted(STATUSES)}): {row}"
    for f, top in (("era", len(ERAS) - 1), ("row", None)):
        v = row[f]
        assert isinstance(v, int) and not isinstance(v, bool) and v >= 0 and (top is None or v <= top), \
            f"tech node {node_id!r}: {f} {v!r} is not an integer in 0..{top if top is not None else ''}: {row}"
    for f in ("title", "branch", "what", "state", "next", "metric", "owner", "doc_id",
              "recommendation", "reasons"):
        v = row.get(f)
        assert v is None or isinstance(v, str), f"tech node {node_id!r}: {f} is not text: {row}"
    updated = row.get("updated_on")
    if updated is not None:
        date.fromisoformat(updated)
    return {"node_id": node_id, **{f: row.get(f) or None for f in FIELDS if f not in ("era", "row")},
            "era": row["era"], "row": row["row"],
            "requires": _parse_requires(row.get("requires"), row)}


def check_tree(nodes: list[dict]) -> None:
    """The tree's invariants across nodes: unique ids, prerequisites that
    exist, no cycle, one node per spot. Raises naming the node."""
    by_id: dict[str, dict] = {}
    for n in nodes:
        assert n["node_id"] not in by_id, f"tech node id {n['node_id']!r} twice: {n}"
        by_id[n["node_id"]] = n
    spots: dict[tuple, str] = {}
    for n in nodes:
        for r in n["requires"]:
            assert r != n["node_id"], f"tech node {n['node_id']!r} requires itself: {n}"
            assert r in by_id, f"tech node {n['node_id']!r} requires {r!r}, which doesn't exist: {n}"
        spot = (n["era"], n["row"])
        assert spot not in spots, \
            f"tech nodes {spots[spot]!r} and {n['node_id']!r} share era {spot[0]} row {spot[1]}: {n}"
        spots[spot] = n["node_id"]
    # a cycle: walk each node's prerequisites, depth first
    state: dict[str, int] = {}          # 1 on the current path, 2 finished

    def walk(nid: str, path: list[str]) -> None:
        if state.get(nid) == 2:
            return
        assert state.get(nid) != 1, f"tech tree cycle: {' -> '.join(path + [nid])}"
        state[nid] = 1
        for r in by_id[nid]["requires"]:
            walk(r, path + [nid])
        state[nid] = 2

    for nid in by_id:
        walk(nid, [])


def _stored(node: dict) -> dict:
    return {**node, "requires": " ".join(node["requires"]) or None}


def _read(client: AitoClient) -> tuple[dict, list[dict]]:
    request = {"from": TABLE, "limit": READ_LIMIT}
    response = client.query(request)
    assert response["total"] <= READ_LIMIT, f"{TABLE}: {response['total']} rows, read {READ_LIMIT}"
    return request, [parse_node(r) for r in response["hits"]]


def tech_tree(client: AitoClient) -> dict:
    """Every node with its prerequisites as a list, plus the eras, the status
    labels and the branches in the order their bands run (by their first
    row). The stored tree is checked first: a broken one raises."""
    request, nodes = _read(client)
    check_tree(nodes)
    nodes.sort(key=lambda n: (n["row"], n["era"]))
    branches: list[str] = []
    for n in nodes:
        if n["branch"] not in branches:
            branches.append(n["branch"])
    return {"eras": ERAS, "statuses": STATUSES, "branches": branches,
            "nodes": nodes, "request": request}


def upsert_tech_node(client: AitoClient, node_id: str, fields: dict,
                     today: str | None = None) -> dict:
    """Write one node by its id. An existing node changes only the fields
    given (a v2 _modify on that row); a new id needs every required field.
    updated_on is stamped, never taken from the caller. Refused, with
    nothing written, if the result would break the tree or link a document
    that doesn't exist. Reads the row back."""
    assert isinstance(node_id, str) and ID.fullmatch(node_id), \
        f"tech node id {node_id!r} is not 1-40 of [a-z0-9-]"
    assert isinstance(fields, dict) and fields, f"tech node {node_id!r}: no fields given"
    unknown = set(fields) - (set(FIELDS) - {"updated_on"})
    assert not unknown, f"tech node {node_id!r}: unknown fields {sorted(unknown)} (one of {FIELDS})"
    today = today or date.today().isoformat()
    _, nodes = _read(client)
    by_id = {n["node_id"]: n for n in nodes}
    existing = by_id.get(node_id)
    if existing is None:
        missing = [f for f in REQUIRED if fields.get(f) in (None, "")]
        assert not missing, f"new tech node {node_id!r}: missing {missing}: {fields}"
    node = parse_node({**(existing or {}), **fields, "node_id": node_id, "updated_on": today})
    check_tree([n for n in nodes if n["node_id"] != node_id] + [node])
    if node["doc_id"]:
        found = client.query({"from": "documents", "where": {"doc_id": node["doc_id"]},
                              "limit": 0})["total"]
        assert found == 1, f"tech node {node_id!r}: doc_id {node['doc_id']!r} is not a document"
    row = _stored(node)
    if existing:
        changed = {f: row[f] for f in list(fields) + ["updated_on"]}
        request = {"update": TABLE, "where": {"node_id": node_id}, "set": changed}
        client.update_entries(TABLE, {"node_id": node_id}, changed)
    else:
        request = {"insert": TABLE, "rows": [row]}
        client.upload_batch(TABLE, [row])
    back = client.query({"from": TABLE, "where": {"node_id": node_id}, "limit": 2})["hits"]
    assert len(back) == 1 and parse_node(back[0]) == node, \
        f"tech node {node_id!r}: wrote {node}, read back {back}"
    action = "updated" if existing else "created"
    changelog.record(client, "tech_node", node_id, action,
                     f"tech node {node['title']}: {', '.join(sorted(fields))}")
    return {"action": action, "node": node, "request": request}
