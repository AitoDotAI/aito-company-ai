"""The knowledge graph: facts about accounts, and questions answered by
traversing the links between them (docs/31-knowledge-graph.md).

The company node is the hub. Contacts, deals and documents each carry a
`company_id` link to it, so Aito can walk the edge in both directions:

    companies  <--company_id--  contacts  <--contact_id--  touches
               <--company_id--  deals
               <--company_id--  documents

**Forward** (child -> parent) is a dotted path: from a contact, the company it
works for is `company_id`, and that company's own columns are
`company_id.relationship`, `company_id.industry`, and so on. That is what lets
"which people work at accounts that pay us?" be one query instead of a join.

**Reverse** (parent -> children) is `$refs.<table>.<fk>`: on a company,
`$refs.contacts.company_id` is the set of contacts pointing at it. Filter that
set with `$exists` to ask "which accounts have a CTO?", or count it with
`$length` for the account's degree.

Every question below is a single Aito query. Nothing here ranks, scores or
filters in Python — the database answers, we render (rule 2).
"""

from . import history, schema
from .aito import AitoClient, AitoError


# Engine v2.11.1 rejects a link path inside a nested `from` ("bit fAnd operation
# requires same sized bit sets, found: 240, 280": the link is counted over the
# whole table), so the two cards whose evidence walks a link predict over all
# deals. The closed-deals filter as outer `where` is no substitute: Aito joins it
# into the evidence (explained-odds read 0.97 instead of 0.71). On v2.11.1 an
# open deal's `won` is null and does not count; a False read from July-era data
# would (test_finished_history lists both cards). Back to history.finished once
# core fixes it.
LINK_IN_NESTED_FROM = "v2.11.1: a link path inside a nested from is a 400"

# every card is POSTed here, `predict` questions included; the card shows it
ENDPOINT = "/api/v2/_query"

# The questions are about THIS deployment's data, not ours. They used to name
# "accounting", "CFO" and "CTO" outright — this repository's home turf — so on
# another company's data the showcase cards came back with nothing. Each
# parameter is now resolved from what is loaded, by an Aito query, and the
# shipped seed resolves to exactly the values the cards always used.

def _ranked(client: AitoClient, request: dict) -> list[str]:
    """The values of one field, most frequent first, as Aito ranks them."""
    try:
        return [h["$value"] for h in client.predict(request).get("hits", [])
                if h.get("$value") not in (None, "", "unknown")]
    except AitoError:          # an empty or young instance: nothing to rank yet
        return []


def focus_industry(client: AitoClient) -> str:
    """The industry with the most deals — where the business actually is. Not
    the highest win rate: that picks a thin segment (analytics, n=20, on the
    seed) whose rate is noise; volume always has rows to show."""
    ranked = _ranked(client, {"from": "deals", "predict": "segment",
                              "select": ["$value", "$p"], "limit": 5})
    fallback = sorted(v for v in schema.SEGMENTS if v != "other") or sorted(schema.SEGMENTS)
    return ranked[0] if ranked else fallback[0]


def typical_role(client: AitoClient, industry: str) -> str:
    """The commonest non-technical role at accounts in `industry`: the person
    you would usually be talking to there. Technical roles are excluded so this
    card and the technical-contact cards ask about different people."""
    ranked = _ranked(client, {"from": "contacts",
                              "where": {"company_id.industry": industry},
                              "predict": "role", "select": ["$value", "$p"], "limit": 10})
    for role in ranked:
        if role not in schema.TECHNICAL_ROLES:
            return role
    return "CEO"


def _technical_clause(path: str) -> dict:
    """"Someone in a technical role is linked here", reached along `path`.

    One role is a single `$exists`. Several must be an `$or` of WHOLE `$exists`
    clauses: the engine rejects an `$or` inside one ("same-member $has condition
    'role' expects a scalar value", v2.11.2) — probed against a live instance,
    not assumed. One role produces exactly the request the card always sent."""
    roles = sorted(schema.TECHNICAL_ROLES)
    clauses = [{path: {"$exists": {"role": r}}} for r in roles]
    return clauses[0] if len(clauses) == 1 else {"$or": clauses}


def technical_label() -> str:
    """How the prose names the technical contact: 'CTO', or 'CTO or Head of IT'."""
    return " or ".join(sorted(schema.TECHNICAL_ROLES))


def _a(word: str) -> str:
    return ("an " if word[:1].upper() in "AEIOU" else "a ") + word


def _plural(role: str) -> str:
    """'CFOs' reads well; 'Head of Financess' does not, so multi-word titles are
    phrased around instead of pluralised."""
    return f"{role}s" if " " not in role else f"people in the {role} role"


def questions(client: AitoClient) -> list[tuple[str, str, dict]]:
    """Each question is (id, prose, request). The prose is the question a person
    actually asks; the request is what the graph makes of it. The view shows
    both, because the point of the demo is that they are close together."""
    industry = focus_industry(client)
    role = typical_role(client, industry)
    tech_label = technical_label()
    return [
        (
            "classify-account",
            "What kind of company is this, judged only by who works there?",
            # Node classification: infer an attribute OF THE ACCOUNT from the set of
            # people linked to it. The account's own industry column is not read —
            # the evidence is the neighbourhood, reached backwards through
            # $refs.contacts.company_id. This is the shape a graph is for, and it is
            # the one card here with no relational equivalent.
            {"from": "companies",
             "where": {"$refs.contacts.company_id": {"$exists": {"role": role}}},
             "predict": "industry", "select": ["$value", "$p"], "limit": 5},
        ),
        (
            "explained-odds",
            f"{_a(industry).capitalize()} account, a champion on board, nothing blocking "
            "— what are the odds?",
            # Several facts at once, one of them reached across the link: the
            # account's industry lives on the company, the champion and the blocker
            # on the deal. $why returns what each of them did to the number, so the
            # answer arrives with its reasons instead of as a bare probability.
            # Over all deals, not history.finished, because of LINK_IN_NESTED_FROM.
            {"from": "deals",
             "where": {"company_id.industry": industry,
                       "champion_present": True,
                       "blocker": "none"},
             "predict": "won", "select": ["$value", "$p", "$why"]},
        ),
        (
            "cto-odds",
            f"At an account where we know {_a(tech_label)}, how likely is a deal to close?",
            # The one card here that a relational database could not also produce.
            # It walks the link FORWARD from the deal to its account, then BACKWARDS
            # to that account's contacts, and asks whether any of them holds a
            # technical role — a fact that exists nowhere on the deal. The view puts
            # the answer next to BASELINE_REQUEST below, because a conditioned
            # probability only means something against the unconditioned one.
            # Over all deals: LINK_IN_NESTED_FROM.
            {"from": "deals",
             "where": _technical_clause("company_id.$refs.contacts.company_id"),
             "predict": "won", "select": ["$value", "$p", "$why"]},
        ),
        (
            "people-at-customers",
            "Who are the people at accounts that pay us?",
            # forward hop: from a contact, through company_id, to that company's
            # harvested relationship. One query instead of a join.
            {"from": "contacts", "where": {"company_id.relationship": "customer"},
             "select": ["name", "role", "company"], "limit": 6},
        ),
        (
            "accounts-with-cto",
            f"Which accounts have {_a(tech_label)} on file?",
            # reverse hop: a company's set of contacts, filtered by $exists
            {"from": "companies",
             "where": _technical_clause("$refs.contacts.company_id"),
             "select": ["name", "industry", "relationship"], "limit": 6},
        ),
        (
            "finance-at-prospects",
            f"Which {_plural(role)} work at accounts we are still selling to?",
            {"from": "contacts",
             "where": {"role": role, "company_id.relationship": "prospect"},
             "select": ["name", "company", "country"], "limit": 6},
        ),
        (
            "accounting-deals",
            f"What is in play across the {industry} industry?",
            {"from": "deals", "where": {"company_id.industry": industry},
             "orderBy": {"$desc": "value_eur"},
             "select": ["company", "stage", "value_eur"], "limit": 6},
        ),
        (
            "most-dealt-with",
            "Which accounts have we opened the most deals with?",
            # degree: the size of the reverse set of DEALS, ordered through a
            # select alias (a $refs path cannot be ordered by directly).
            {"from": "companies",
             "select": ["name", "relationship", "mrr_eur",
                        {"deal_count": {"$length": "$refs.deals.company_id.stage"}}],
             "orderBy": {"$desc": "deal_count"}, "limit": 6},
        ),
    ]



# The same prediction with NO condition. Quoting a conditioned probability
# without this is how "50%" once got reported as a finding when the base rate
# was 25% — and how a 27% result can look decisive at 73/27 while saying
# nothing. Computed, never written down: every time these numbers were typed
# into prose they drifted the next time the seed was regenerated.
BASELINE_REQUEST = {"from": history.finished("deals"), "predict": "won", "select": ["$value", "$p"]}


def _p_true(hits: list[dict]) -> float | None:
    """P(won = true) out of a predict response."""
    hit = next((h for h in hits if h.get("$value") in (True, "true")), None)
    return hit["$p"] if hit else None


def answer(client: AitoClient, question_id: str, prose: str, request: dict) -> dict:
    """Run one question. A failure is reported, not swallowed: this is a
    deliberately un-battle-tested corner of Aito, and a card that says which
    query broke and how is worth more than a view that refuses to render."""
    out = {"id": question_id, "question": prose, "endpoint": ENDPOINT, "request": request}
    try:
        try:
            response = client.query(request)
        except AitoError as error:
            # no closed deal yet: a state the card says, not a failure
            if not history.is_empty_population(error):
                raise
            out.update(hits=[], total=0, no_history=True)
            return out
        _shape(out, response)
    except Exception as exc:                      # noqa: BLE001 — reported, see above
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _shape(out: dict, response: dict) -> None:
    """Fill a card from its query's response."""
    hits = response.get("hits", [])
    # $why comes back as a nested tree that is far too big to render raw.
    # Flatten it to the labelled lift factors the dashboard already uses for
    # deal close-likelihood, strongest effect first, and drop the tree.
    if any("$why" in h for h in hits):
        from . import aitowhy
        from .deals import _why_label
        true_hit = next((h for h in hits if h.get("$value") in (True, "true")), None)
        if true_hit is not None:
            factors = [{"label": _why_label(f["proposition"]), "lift": f["value"]}
                       for f in aitowhy.lift_factors(true_hit)]
            factors.sort(key=lambda w: -abs(w["lift"] - 1.0))
            out["why"] = factors[:6]
            out["p"] = true_hit.get("$p")
        hits = [{k: v for k, v in h.items() if k != "$why"} for h in hits]
    out["hits"] = hits
    out["total"] = response.get("total")


def board(client: AitoClient) -> dict:
    """Every question, each with the query that answered it."""
    # the base rate is a card too: the view quotes it, so its query is on the page
    cards = list(questions(client)) + [
        ("baseline", "How likely is any closed deal to have been won?", BASELINE_REQUEST)]
    # every card in ONE _batch round trip; if any card's query fails, the batch
    # does too, so fall back to one query per card, where each failure is
    # reported on its own card (td-20261014123607349120)
    try:
        responses = client.batch([req for _, _, req in cards])
    except AitoError:
        responses = None
    if responses is None:
        answers = [answer(client, qid, prose, req) for qid, prose, req in cards]
    else:
        answers = []
        for (qid, prose, req), response in zip(cards, responses):
            out = {"id": qid, "question": prose, "endpoint": ENDPOINT, "request": req}
            _shape(out, response)
            answers.append(out)
    base = answers[-1]
    conditioned = next((a for a in answers if a["id"] == "cto-odds"), None)
    return {
        "answers": answers,
        # the lift, for the view to state honestly: both sides measured, neither
        # written down.
        "baseline_p": _p_true(base.get("hits", [])),
        "conditioned_p": _p_true((conditioned or {}).get("hits", [])),
        # the view names the condition in prose, so it reads the label from here
        # rather than assuming which role this deployment counts as technical
        "technical_role": technical_label(),
        "ok": sum(1 for a in answers if "error" not in a),
        "failed": [a["id"] for a in answers if "error" in a],
    }


# ---- the graph itself: nodes and links (the explorer view, MCP graph_search) ----

NODE_KINDS = ("company", "contact", "deal", "document", "touch", "fact")
# drawn only when one account is unfolded (docs/41): across every account they
# would bury the graph
FOCUS_KINDS = ("touch", "fact")
COMPANY_FACTS = ("industry", "relationship", "country", "mrr_eur", "open_deals",
                 "contact_count", "technical_contact")
# the company facts a caller may filter on; the filter crosses the link
# (company_id.<fact>) so Aito, not Python, picks the neighbourhood
FILTER_FACTS = ("industry", "relationship", "country")


def network(client: AitoClient, query: str | None = None, kinds: list[str] | None = None,
            industry: str | None = None, relationship: str | None = None,
            country: str | None = None, focus: str | None = None) -> dict:
    """The knowledge graph as nodes and links: companies, the contacts and
    deals linked to them by company_id, and the documents about them (and the
    contact a document names). `industry`/`relationship`/`country` filter the
    companies in Aito, and the other tables through the forward link
    (`company_id.relationship`), so the neighbourhood is one query per table.
    `query` is a literal lookup over node labels, like the top-bar finder
    (search.quick_find): the matches stay with their one-hop neighbourhood.
    If fuzzy matching is wanted, this lookup can move to the search index
    (search.serve), which ranks in Aito.
    No ranking or scoring here (rule 2): the order is the database's, then by
    label for a stable layout.

    `focus` unfolds ONE account (docs/41): the company, its contacts, deals,
    documents and touches, and its active account facts, each fact linked to
    the record it came from (`said_in`) or marked external or dangling. The
    company node also carries the `basis` of each harvested fact (the rows it
    was derived from, by the load-time rule) and its `hold`."""
    if focus is not None:
        return _unfold(client, focus, kinds)
    kinds = list(kinds or ("company", "contact", "deal"))
    if set(kinds) & set(FOCUS_KINDS):
        raise AssertionError(f"{sorted(set(kinds) & set(FOCUS_KINDS))} are drawn only with focus")
    unknown = set(kinds) - set(NODE_KINDS)
    assert not unknown, f"unknown node kinds {sorted(unknown)}; have {list(NODE_KINDS)}"
    filters = {k: v for k, v in (("industry", industry), ("relationship", relationship),
                                 ("country", country)) if v}
    requests = []

    def q(table: str, where: dict, select: list[str]) -> list[dict]:
        request = {"from": table, "select": select, "limit": 100000}
        if where:
            request["where"] = where
        requests.append(request)
        return client.query(request)["hits"]

    linked = {f"company_id.{k}": v for k, v in filters.items()}
    companies = q("companies", dict(filters), ["company_id", "name", *COMPANY_FACTS])
    # the filter choices come from every company, so a chosen filter does not
    # hide the values it could change to
    facet_rows = q("companies", {}, list(FILTER_FACTS)) if filters else companies
    contacts = q("contacts", linked, ["contact_id", "name", "role", "tier", "company_id"]) \
        if "contact" in kinds else []
    deals = q("deals", linked, ["deal_id", "stage", "value_eur", "company_id"]) \
        if "deal" in kinds else []
    documents = q("documents", linked,
                  ["doc_id", "title", "noted_on", "company_id", "stakeholder_id"]) \
        if "document" in kinds else []

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for c in companies:
        nodes[f"company:{c['company_id']}"] = {
            "id": f"company:{c['company_id']}", "kind": "company", "label": c["name"],
            "company_id": c["company_id"], "facts": {k: c.get(k) for k in COMPANY_FACTS}}
    for c in contacts:
        nodes[f"contact:{c['contact_id']}"] = {
            "id": f"contact:{c['contact_id']}", "kind": "contact", "label": c["name"],
            "role": c.get("role"), "tier": c.get("tier"), "company_id": c["company_id"]}
        edges.append({"source": f"contact:{c['contact_id']}",
                      "target": f"company:{c['company_id']}", "kind": "works_at"})
    for d in deals:
        nodes[f"deal:{d['deal_id']}"] = {
            "id": f"deal:{d['deal_id']}", "kind": "deal", "label": d["stage"],
            "stage": d["stage"], "value_eur": d.get("value_eur"), "company_id": d["company_id"]}
        edges.append({"source": f"deal:{d['deal_id']}",
                      "target": f"company:{d['company_id']}", "kind": "deal_with"})
    # a note linked to no company has no edge to draw: counted, not drawn
    unlinked_documents = sum(1 for d in documents if not d.get("company_id"))
    for d in documents:
        if not d.get("company_id"):
            continue
        nodes[f"document:{d['doc_id']}"] = {
            "id": f"document:{d['doc_id']}", "kind": "document", "label": d["title"],
            "noted_on": d.get("noted_on"), "company_id": d["company_id"]}
        edges.append({"source": f"document:{d['doc_id']}",
                      "target": f"company:{d['company_id']}", "kind": "about"})
        if d.get("stakeholder_id"):
            edges.append({"source": f"document:{d['doc_id']}",
                          "target": f"contact:{d['stakeholder_id']}", "kind": "mentions"})
    # a link to a node outside the loaded set (an unloaded kind, a filtered-out
    # company) is dropped and counted, never drawn dangling
    edges_out = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    dropped = len(edges) - len(edges_out)

    matched: list[str] = []
    if query and query.strip():
        needle = query.strip().lower()
        matched = sorted(nid for nid, n in nodes.items()
                         if needle in (n["label"] or "").lower()
                         or needle in (n.get("role") or "").lower())
        keep = set(matched)
        for e in edges_out:
            if e["source"] in matched:
                keep.add(e["target"])
            if e["target"] in matched:
                keep.add(e["source"])
        nodes = {nid: n for nid, n in nodes.items() if nid in keep}
        edges_out = [e for e in edges_out if e["source"] in nodes and e["target"] in nodes]

    ordered = sorted(nodes.values(), key=lambda n: (NODE_KINDS.index(n["kind"]), n["label"] or ""))
    counts: dict[str, int] = {}
    for n in ordered:
        counts[n["kind"]] = counts.get(n["kind"], 0) + 1
    return {
        "nodes": ordered, "edges": edges_out, "counts": counts, "matched": matched,
        "query": query or None, "filters": filters, "kinds": kinds,
        "facets": {k: sorted({c[k] for c in facet_rows if c.get(k)}) for k in FILTER_FACTS},
        "dropped_edges": dropped, "unlinked_documents": unlinked_documents,
        "requests": requests,
    }


def _unfold(client: AitoClient, company_id: str, kinds: list[str] | None) -> dict:
    """network(focus=...): one account as a graph (docs/41). One query per
    table on company_id (touches through their contact), plus one per source
    table for the facts' records. Grouping and lookups only (rule 2)."""
    from . import facts as facts_mod
    from .loaders import harvest
    kinds = list(kinds or NODE_KINDS)
    unknown = set(kinds) - set(NODE_KINDS)
    if unknown:
        raise AssertionError(f"unknown node kinds {sorted(unknown)}; have {list(NODE_KINDS)}")
    requests = []

    def q(table: str, where: dict, select: list[str] | None = None) -> list[dict]:
        request = {"from": table, "where": where, "limit": 100000}
        if select:
            request["select"] = select
        requests.append(request)
        return client.query(request)["hits"]

    def record(request: dict) -> dict:
        requests.append(request)
        return client.query(request)

    found = q("companies", {"company_id": company_id}, ["company_id", "name", *COMPANY_FACTS])
    if not found:
        raise LookupError(f"no company with company_id {company_id!r}")
    co = found[0]
    contacts = q("contacts", {"company_id": company_id},
                 ["contact_id", "name", "role", "tier", "segment", "country", "company_id"])
    deals = q("deals", {"company_id": company_id},
              ["deal_id", "stage", "value_eur", "segment", "company_id"])
    documents = q("documents", {"company_id": company_id},
                  ["doc_id", "title", "noted_on", "company_id", "stakeholder_id"])
    touches = q("touches", {"contact_id.company_id": company_id},
                ["touch_id", "contact_id", "deal_id", "ts", "channel", "outcome"])
    requests.append({"schema": "GET /api/v2/schema"})   # does this instance have facts yet
    every = q("facts", {"company_id": company_id}) if "facts" in client.get_schema()["schema"] else []
    active = [f for f in every if not f.get("superseded_by")]

    stored, basis = harvest(contacts, deals)
    for field, b in basis.items():
        b["matches"] = b["value"] == co.get(field)
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    cnode = f"company:{company_id}"
    nodes[cnode] = {"id": cnode, "kind": "company", "label": co["name"], "company_id": company_id,
                    "facts": {k: co.get(k) for k in COMPANY_FACTS}, "basis": basis,
                    "hold": facts_mod._hold(every, active)["status"]}

    def touch_node(h: dict, foreign: bool = False) -> dict:
        return {"id": f"touch:{h['touch_id']}", "kind": "touch",
                "label": f"{h.get('channel') or 'touch'} {(h.get('ts') or '')[:10]}".strip(),
                "ts": h.get("ts"), "outcome": h.get("outcome"), "contact_id": h.get("contact_id"),
                **({"foreign": True} if foreign else {})}

    def document_node(d: dict, foreign: bool = False) -> dict:
        return {"id": f"document:{d['doc_id']}", "kind": "document", "label": d["title"],
                "noted_on": d.get("noted_on"), "company_id": d.get("company_id"),
                **({"foreign": True} if foreign else {})}

    if "contact" in kinds:
        for c in contacts:
            nodes[f"contact:{c['contact_id']}"] = {
                "id": f"contact:{c['contact_id']}", "kind": "contact", "label": c["name"],
                "role": c.get("role"), "tier": c.get("tier"), "company_id": company_id}
            edges.append({"source": f"contact:{c['contact_id']}", "target": cnode, "kind": "works_at"})
    if "deal" in kinds:
        for d in deals:
            nodes[f"deal:{d['deal_id']}"] = {
                "id": f"deal:{d['deal_id']}", "kind": "deal", "label": d["stage"],
                "stage": d["stage"], "value_eur": d.get("value_eur"), "company_id": company_id}
            edges.append({"source": f"deal:{d['deal_id']}", "target": cnode, "kind": "deal_with"})
    if "document" in kinds:
        for d in documents:
            nodes[f"document:{d['doc_id']}"] = document_node(d)
            edges.append({"source": f"document:{d['doc_id']}", "target": cnode, "kind": "about"})
            if d.get("stakeholder_id"):
                edges.append({"source": f"document:{d['doc_id']}",
                              "target": f"contact:{d['stakeholder_id']}", "kind": "mentions"})
    if "touch" in kinds:
        for h in touches:
            nodes[f"touch:{h['touch_id']}"] = touch_node(h)
            edges.append({"source": f"touch:{h['touch_id']}", "target": f"contact:{h['contact_id']}",
                          "kind": "touched"})
            if h.get("deal_id"):
                edges.append({"source": f"touch:{h['touch_id']}", "target": f"deal:{h['deal_id']}",
                              "kind": "on_deal"})
    if "fact" in kinds:
        sources = facts_mod.find_sources(client, active, query=record)
        for f in sorted(active, key=lambda f: (f["valid_from"], f["fact_id"])):
            fid = f"fact:{f['fact_id']}"
            src = facts_mod.source_of(f, sources)
            nodes[fid] = {"id": fid, "kind": "fact", "label": f["statement"], "fact_kind": f["kind"],
                          "slot": f.get("slot"), "state": f.get("state"), "due": f.get("due"),
                          "valid_from": f["valid_from"], "source": src, "company_id": company_id}
            edges.append({"source": fid, "target": cnode, "kind": "fact_of"})
            if f.get("stakeholder_id"):
                edges.append({"source": fid, "target": f"contact:{f['stakeholder_id']}", "kind": "concerns"})
            node_kind = src["node"].split(":", 1)[0] if src["node"] else None
            if node_kind in kinds:
                # a source on another account is still this fact's record: drawn,
                # marked foreign, and counted apart from this account's own
                if src["node"] not in nodes:
                    row = sources[(f["source_kind"], f["source_id"])]
                    nodes[src["node"]] = (document_node(row, foreign=True) if node_kind == "document"
                                          else touch_node(row, foreign=True))
                edges.append({"source": fid, "target": src["node"], "kind": "said_in"})
    edges_out = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    ordered = sorted(nodes.values(), key=lambda n: (NODE_KINDS.index(n["kind"]), n["label"] or ""))
    counts: dict[str, int] = {}
    foreign: dict[str, int] = {}
    for n in ordered:
        tally = foreign if n.get("foreign") else counts
        tally[n["kind"]] = tally.get(n["kind"], 0) + 1
    return {"nodes": ordered, "edges": edges_out, "counts": counts, "foreign_sources": foreign,
            "matched": [cnode],
            "query": None, "filters": {}, "kinds": kinds, "focus": company_id,
            "facets": {}, "dropped_edges": len(edges) - len(edges_out),
            "unlinked_documents": 0, "requests": requests}
