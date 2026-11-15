# 45 — The tech tree

Aito's product and research lines as a map: what is researched, what is in
progress, what is ready to start, what waits on the operator's decision, and
what is locked behind something else. The CPO drew it first as a one-off page;
this makes it a record the lanes keep current, read by a view, by MCP, and by
any agent that asks what unlocks what.

## The data

One collection, `tech_nodes`, one row per node:

| field | |
|---|---|
| `node_id` | 1–40 of `[a-z0-9-]` |
| `title`, `metric` | the card: a name and one short line |
| `branch` | the band it sits in (Knowledge, Inference, …), free text |
| `era` | the column, 0–4: Foundations, Proven, Hardening, Customer-ready, In market |
| `row` | its row; a branch's band spans its nodes' rows |
| `status` | `done` (Researched), `active` (In progress), `open` (Ready to start), `decision` (Your decision), `locked` |
| `what`, `state`, `next` | the panel: what it is, where it stands, the next step |
| `owner` | the lane or person, free text |
| `requires` | prerequisite node ids, stored space-separated in a String (never tokenised) and returned as a list |
| `doc_id` | the article, a `documents` row |
| `updated_on` | stamped on every write |

The tree holds to these, on read and on write (rule 3): every prerequisite
exists; no node requires itself and there is no cycle; no two nodes share an
era and row; a `doc_id` names a real document; values are in the vocabulary.
A stored tree that breaks one raises with the node instead of drawing a wrong
map. Nothing in it is predicted: it is a record, drawn as it is.

## Reading and writing

- `tech_tree()` (MCP) and `GET /api/tech-tree`: every node, with `eras`,
  `statuses` (status → label) and `branches` in band order.
- `upsert_tech_node(node_id, fields)` (MCP): one node by its id. An existing
  node changes only the fields given, as a v2 `_modify` on that row; a new id
  needs title, branch, era, row, status, what, state and next. Anything that
  would break the tree is refused with nothing written. The row is read back,
  and the change is logged (`changelog`, entity `tech_node`).

## The view

Knowledge → Tech tree. Eras run left to right, branches as bands, each
prerequisite a curve. Hovering a node lights its whole prerequisite chain;
clicking opens the panel (what, state, next, owner, requires, unlocks, and the
article when `doc_id` is set, linking `#/documents/<doc_id>`); the legend
filters by status. The map scrolls sideways inside its own box, so it reads on
a phone. In-app `#/` links in a document open in the same tab, so articles can
link to each other.

## Data and privacy

The seed (`data/seed/tech_nodes.csv`) is an invented tree in the same shape.
The real tree describes customers, partners and open decisions, so it never
enters this repository: it is loaded into the operator's instance by a
git-ignored maintenance script, and kept current there with `upsert_tech_node`.

## Not built

Positions are hand-set (era and row). Laying the tree out automatically, or
deriving a status from tickets, is not part of this; propose it first.
