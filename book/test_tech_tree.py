"""The tech tree: product and research lines as nodes with prerequisites
(docs/45). Nodes live in the `tech_nodes` collection; `tech_tree` reads them
all with `requires` parsed to a list, and `upsert_tech_node` writes one node
by its id, refusing anything that would make the tree wrong: an unknown
prerequisite, a cycle, an id outside [a-z0-9-], a value outside the
vocabulary, two nodes on one spot, or a document that doesn't exist.

The seed (data/seed/tech_nodes.csv) is a small invented tree in the same
shape as the real one, which never enters this repository.
"""

import json

import booktest as bt

from company_ai import loaders, techtree
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _seeded() -> AitoClient:
    client = _client()
    loaders.create_schema(client)
    loaders.load_documents(client, SEED_DIR)
    loaders.load_tech_nodes(client, SEED_DIR)
    return client


def _refused(t: bt.TestCaseRun, label: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        t.tln(f"  {label}: refused — {e}")
        return
    raise AssertionError(f"{label}: was accepted")


def test_the_tree_reads_with_parsed_prerequisites(t: bt.TestCaseRun) -> None:
    """Every node with its prerequisites as a list of ids, and every id it
    names exists. The eras and statuses come with it, so a view needs no
    vocabulary of its own."""
    client = _seeded()
    tree = techtree.tech_tree(client)
    t.tln(f"request: {json.dumps(tree['request'], sort_keys=True)}")
    t.tln(f"eras: {tree['eras']}")
    t.tln(f"statuses: {tree['statuses']}")
    t.tln(f"branches (top to bottom): {tree['branches']}")
    t.tln(f"{len(tree['nodes'])} nodes:")
    for n in tree["nodes"]:
        t.tln(f"  {n['node_id']:4s} era {n['era']} row {n['row']:2d} {n['status']:8s} "
              f"{n['title']} <- {n['requires']}")
    ids = {n["node_id"] for n in tree["nodes"]}
    assert all(isinstance(n["requires"], list) for n in tree["nodes"])
    assert all(r in ids for n in tree["nodes"] for r in n["requires"])
    assert {n["status"] for n in tree["nodes"]} <= set(techtree.STATUSES)


def test_upsert_writes_one_node_by_its_id(t: bt.TestCaseRun) -> None:
    """An update changes only the fields given and stamps updated_on; it is a
    v2 _modify on that one row. A new id is created whole. Both read back."""
    client = _seeded()
    before = {n["node_id"]: n for n in techtree.tech_tree(client)["nodes"]}
    target = next(n for n in before.values() if n["status"] == "active")

    t.h1("Update: the active node is done")
    out = techtree.upsert_tech_node(client, target["node_id"],
                                    {"status": "done", "state": "Finished in the seed."},
                                    today="2026-11-15")
    t.tln(f"  action: {out['action']}, request: {json.dumps(out['request'], sort_keys=True)}")
    after = {n["node_id"]: n for n in techtree.tech_tree(client)["nodes"]}
    changed = {k for k in after[target["node_id"]] if after[target["node_id"]][k] != target[k]}
    t.tln(f"  fields that changed: {sorted(changed)}")
    assert changed == {"status", "state", "updated_on"}, changed
    assert len(after) == len(before)

    t.h1("Create: a new node that requires two existing ones")
    reqs = sorted(before)[:2]
    era = max(before[r]["era"] for r in reqs) + 1
    out = techtree.upsert_tech_node(client, "new-line", {
        "title": "A new line", "branch": before[reqs[0]]["branch"], "era": era, "row": 40,
        "status": "locked", "metric": "not started", "what": "Something new.",
        "state": "Planned.", "next": "Wait for its prerequisites.", "owner": "operator",
        "requires": reqs}, today="2026-11-15")
    t.tln(f"  action: {out['action']}, node: {json.dumps(out['node'], sort_keys=True)}")
    tree = techtree.tech_tree(client)
    assert next(n for n in tree["nodes"] if n["node_id"] == "new-line")["requires"] == reqs
    loaders.load_tech_nodes(client, SEED_DIR)       # leave the seed as it was


def test_upsert_refuses_what_would_make_the_tree_wrong(t: bt.TestCaseRun) -> None:
    """Rule 3: each of these raises with the offending node, and nothing is
    written."""
    client = _seeded()
    nodes = {n["node_id"]: n for n in techtree.tech_tree(client)["nodes"]}
    child = next(n for n in nodes.values() if n["requires"])
    parent = child["requires"][0]
    up = lambda node_id, fields: techtree.upsert_tech_node(client, node_id, fields,  # noqa: E731
                                                           today="2026-11-15")

    _refused(t, "a cycle (the prerequisite requires its child)",
             lambda: up(parent, {"requires": nodes[parent]["requires"] + [child["node_id"]]}))
    _refused(t, "a node requiring itself", lambda: up(parent, {"requires": [parent]}))
    _refused(t, "an unknown prerequisite", lambda: up(parent, {"requires": ["no-such-node"]}))
    _refused(t, "an id with a space", lambda: up("two words", {"title": "x"}))
    _refused(t, "an id with a capital", lambda: up("Abc", {"title": "x"}))
    _refused(t, "a status outside the vocabulary", lambda: up(parent, {"status": "maybe"}))
    _refused(t, "an era past the last", lambda: up(parent, {"era": len(techtree.ERAS)}))
    _refused(t, "a field the node doesn't have", lambda: up(parent, {"colour": "red"}))
    other = next(n for n in nodes.values() if n["node_id"] != parent)
    _refused(t, "two nodes on one spot",
             lambda: up(parent, {"era": other["era"], "row": other["row"]}))
    _refused(t, "a document that doesn't exist", lambda: up(parent, {"doc_id": "no-such-doc"}))
    _refused(t, "a new node missing its title", lambda: up("half-made", {"branch": "x"}))

    after = {n["node_id"]: n for n in techtree.tech_tree(client)["nodes"]}
    assert after == nodes, "a refused upsert changed the tree"
    t.tln("the tree is unchanged")
