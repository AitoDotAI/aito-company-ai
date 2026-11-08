"""Account facts (docs/39): short, sourced statements per account, superseded
but never deleted. `list_facts` reads them; `group` turns one account's facts
into the briefing's groups. Grouping and sorting by kind, slot and date only:
nothing is ranked, scored or inferred (rule 2). The writes are log.add_fact and
log.supersede_fact.
"""

from . import schema
from .aito import AitoClient
from .loaders import company_slug

# the slots where two active facts are a conflict. Two champions or sponsors
# are normal on a real account, and flagging them would teach people to ignore
# the list (CPO review of #75).
CONFLICT_SLOTS = ("decision_owner",)
ROLE_ORDER = ("champion", "decision_owner", "sponsor", "signer", "other")
ATTRIBUTE_ORDER = ("pain", "budget_cycle", "procurement", "deployment", "billing_model",
                   "tooling", "headcount", "other")


# where a fact's source can be stored (docs/41): kind -> (table, key, node kind).
# A call is a touch when it was logged as one; mail isn't stored (no mail
# ingest), and an antti source is an operator statement.
# the columns read for a source record: never a document body (CPO review of #83)
SOURCE_SELECT = {"documents": ["doc_id", "title", "noted_on", "company_id", "stakeholder_id"],
                 "touches": ["touch_id", "contact_id", "deal_id", "ts", "channel", "outcome"]}
SOURCE_LIMIT = 10000
STORED_SOURCES = {"doc": ("documents", "doc_id", "document"),
                  "touch": ("touches", "touch_id", "touch"),
                  "call": ("touches", "touch_id", "touch")}
# a doc or touch source that isn't stored is dangling, and add_fact warns
MUST_RESOLVE = ("doc", "touch")


def find_sources(client: AitoClient, facts: list[dict], query=None) -> dict[tuple[str, str], dict]:
    """(source_kind, source_id) -> the stored row it names, for every fact
    whose source kind can be stored and is. One query per table, through
    `query(request)` when given (so a caller can list its requests). Reads
    SOURCE_SELECT only, never a body. A lookup, no ranking."""
    if query is None:
        def query(request):
            return client.query(request)
    wanted: dict[str, set[str]] = {}
    for f in facts:
        if f["source_kind"] in STORED_SOURCES:
            wanted.setdefault(STORED_SOURCES[f["source_kind"]][0], set()).add(f["source_id"])
    found: dict[tuple[str, str], dict] = {}
    for table, ids in sorted(wanted.items()):
        key = next(k for t, k, _ in STORED_SOURCES.values() if t == table)
        response = query({"from": table, "where": {key: {"$or": sorted(ids)}},
                          "select": SOURCE_SELECT[table], "limit": SOURCE_LIMIT})
        if response["total"] > SOURCE_LIMIT:
            raise AssertionError(f"{table}: {response['total']} rows for {len(ids)} source ids")
        hits = response["hits"]
        for h in hits:
            for kind, (t, k, _) in STORED_SOURCES.items():
                if t == table:
                    found[(kind, h[k])] = h
    return found


def source_of(fact: dict, found: dict[tuple[str, str], dict]) -> dict:
    """A fact's source with its status (docs/41): linked (stored; `node` names
    it), external (a kind that isn't stored here), or dangling (a doc or touch
    id that names nothing)."""
    kind, sid = fact["source_kind"], fact["source_id"]
    out = {"kind": kind, "id": sid, "node": None}
    if (kind, sid) in found:
        out.update(status="linked", node=f"{STORED_SOURCES[kind][2]}:{sid}")
    elif kind in MUST_RESOLVE:
        out["status"] = "dangling"
    else:
        out["status"] = "external"
    return out


def source_warnings(client: AitoClient, fact: dict) -> list[str]:
    """add_fact's warnings: a doc or touch source that names nothing stored.
    The fact is accepted as before; refusing it is Antti's option (docs/41)."""
    try:
        src = source_of(fact, find_sources(client, [fact]))
    except Exception as e:   # the fact is already written: say so, don't fail the write
        return [f"could not check source {fact['source_kind']}:{fact['source_id']}: {e}"]
    return [f"source {src['kind']}:{src['id']} not found"] if src["status"] == "dangling" else []


READ_LIMIT = 10000


def _whole(response: dict, table: str, limit: int) -> None:
    """A read must return every row it matched: past its limit it raises
    rather than answering from a truncated page (rule 3)."""
    if response["total"] > limit:
        raise AssertionError(f"{table}: {response['total']} rows match, over the {limit} read here")


def _company_id(client: AitoClient, company: str) -> str:
    """A company_id, or the slug of an exact name. Unknown raises."""
    for cid in (company, company_slug(company)):
        if client.query({"from": "companies", "where": {"company_id": cid}, "limit": 0})["total"]:
            return cid
    raise LookupError(f"no company with company_id or name {company!r}")


def list_facts(client: AitoClient, company: str, active_only: bool = True) -> list[dict]:
    """One account's facts, newest valid_from first (then fact_id, for a stable
    order). `active_only` leaves out the superseded ones."""
    where = {"company_id": _company_id(client, company)}
    response = client.query({"from": "facts", "where": where, "limit": READ_LIMIT})
    _whole(response, "facts", READ_LIMIT)
    rows = response["hits"]
    if active_only:
        rows = [r for r in rows if not r.get("superseded_by")]
    return sorted(rows, key=lambda r: (r["valid_from"], r["fact_id"]), reverse=True)


# a ledger row's status (docs/43 §4), computed at read, never stored. The
# conflict and unconfirmed statuses arrive with slices 3 and 4.
LEDGER_STATUSES = ("active", "superseded", "review: source missing", "review: source changed")
EDITABLE_SOURCES = {"doc": "documents"}   # a source kind whose edits reach the change log


def ledger(client: AitoClient, company: str | None = None, kind: str | None = None,
           slot: str | None = None, source_id: str | None = None,
           status: str | None = None) -> dict:
    """Every fact matching the filters, each with its source resolved and its
    status (docs/43): superseded; review: source missing (a doc or touch that
    names nothing); review: source changed (the source document was edited
    after the fact was attached, by the change log); else active. Exact
    lookups and dates only, nothing ranked (rule 2); an unknown filter value
    raises (rule 3). Returns {facts, count, requests}."""
    if kind is not None and kind not in schema.FACT_KINDS:
        raise AssertionError(f"unknown kind {kind!r}; known {sorted(schema.FACT_KINDS)}")
    slots = set().union(*schema.FACT_SLOTS.values())
    if slot is not None and slot not in slots:
        raise AssertionError(f"unknown slot {slot!r}; known {sorted(slots)}")
    if status is not None and status not in LEDGER_STATUSES:
        raise AssertionError(f"unknown status {status!r}; known {list(LEDGER_STATUSES)}")
    requests: list[dict] = []

    def query(request: dict) -> dict:
        requests.append(request)
        return client.query(request)

    where = {k: v for k, v in (("company_id", company and _company_id(client, company)),
                               ("kind", kind), ("slot", slot), ("source_id", source_id)) if v}
    request = {"from": "facts", "limit": READ_LIMIT}
    if where:
        request["where"] = where
    response = query(request)
    _whole(response, "facts", READ_LIMIT)
    rows = response["hits"]
    found = find_sources(client, rows, query=query)
    edited = _last_edits(query, rows)
    out = []
    for f in rows:
        src = source_of(f, found)
        if f.get("superseded_by"):
            st = "superseded"
        elif src["status"] == "dangling":
            st = "review: source missing"
        elif edited.get((f["source_kind"], f["source_id"]), "") > f["created_at"]:
            st = "review: source changed"
        else:
            st = "active"
        if status is None or st == status:
            out.append({**f, "source": src, "status": st})
    out.sort(key=lambda r: (r["company_id"], r["valid_from"], r["fact_id"]), reverse=True)
    return {"facts": out, "count": len(out), "requests": requests}


def _last_edits(query, rows: list[dict]) -> dict[tuple[str, str], str]:
    """(source_kind, source_id) -> when that source was last edited, from the
    change log's `updated` rows, for the sources whose edits are logged."""
    last: dict[tuple[str, str], str] = {}
    for kind, entity in EDITABLE_SOURCES.items():
        ids = sorted({f["source_id"] for f in rows if f["source_kind"] == kind})
        if not ids:
            continue
        response = query({"from": "changelog", "limit": READ_LIMIT, "select": ["entity_id", "at"],
                          "where": {"entity": entity, "action": "updated",
                                    "entity_id": {"$or": ids}}})
        _whole(response, "changelog", READ_LIMIT)
        for h in response["hits"]:
            key = (kind, h["entity_id"])
            last[key] = max(last.get(key, ""), h["at"])
    return last


def _hold(every: list[dict], active: list[dict]) -> dict:
    """The account's hold status, failing closed (docs/39, CRO 6.11.2026): one
    active on_hold from antti is HOLD; any anomaly is HOLD (unclear: reason);
    `released` only when a release from antti superseded the hold."""
    holds = [f for f in active if f["kind"] == "hold"]
    replaced_by = {f["superseded_by"] for f in every if f["kind"] == "hold"
                   and f.get("state") == "on_hold" and f.get("superseded_by")}
    reasons = []
    if len(holds) >= 2:
        reasons.append(f"two active holds ({', '.join(f['fact_id'] for f in holds)})")
    if any(f.get("state") == "released" and f["fact_id"] not in replaced_by for f in holds):
        reasons.append("a release that supersedes no hold")
    # an active foreign-source hold can only have come by a direct load; it
    # keeps the account unclear until Antti's hold or release supersedes it
    reasons += [f"a hold fact with source {f['source_kind']} ({f['fact_id']})"
                for f in holds if f["source_kind"] != schema.HOLD_SOURCE]
    if reasons:
        status = f"HOLD (unclear: {'; '.join(reasons)})"
    elif any(f.get("state") == "on_hold" for f in holds):
        status = "HOLD"
    elif holds:
        status = "released"
    else:
        status = None
    return {"status": status, "facts": holds}


def group(every: list[dict], names: dict[str, str]) -> dict:
    """One account's facts (all of them, superseded too) as the briefing's
    groups. Only active facts are shown; superseded ones are read only to say
    what a decision replaced and whether a hold was released. `names` maps a
    contact_id to its name."""
    active = sorted((f for f in every if not f.get("superseded_by")),
                    key=lambda f: (f["valid_from"], f["fact_id"]), reverse=True)
    replaced = {}
    for f in every:
        if f.get("superseded_by"):
            replaced.setdefault(f["superseded_by"], []).append(f["fact_id"])

    def row(f: dict) -> dict:
        out = {"statement": f["statement"], "kind": f["kind"], "slot": f.get("slot"),
               "state": f.get("state"), "due": f.get("due"),
               "stakeholder_id": f.get("stakeholder_id"),
               "stakeholder": names.get(f.get("stakeholder_id")) if f.get("stakeholder_id") else None,
               "source_kind": f["source_kind"], "source_id": f["source_id"],
               "source": {"kind": "fact", "id": f["fact_id"], "date": f["valid_from"]}}
        if f["kind"] == "decision":
            out["replaces"] = sorted(replaced.get(f["fact_id"], []))
        if f["kind"] == "commitment":
            out["label"] = "sent" if f["state"] == "sent" else "drafted, not sent"
        return out

    of = lambda kind: [row(f) for f in active if f["kind"] == kind]
    roles = {slot: [row(f) for f in active if f["kind"] == "role" and f["slot"] == slot]
             for slot in ROLE_ORDER}
    hold = _hold(every, active)
    conflicts = [{"slot": slot, "facts": roles[slot]} for slot in CONFLICT_SLOTS
                 if len(roles[slot]) >= 2]
    if len(hold["facts"]) >= 2:
        conflicts.append({"slot": "hold", "facts": [row(f) for f in hold["facts"]]})
    contact = of("contact_info")
    return {
        "hold": {"status": hold["status"], "facts": [row(f) for f in hold["facts"]]},
        "roles": roles,
        # newest first within a slot (active is sorted so); not conflicts (docs/42)
        "attributes": {slot: [row(f) for f in active if f["kind"] == "attribute" and f["slot"] == slot]
                       for slot in ATTRIBUTE_ORDER},
        "conflicts": conflicts,
        "decisions": of("decision"),
        "open_questions": of("open_question"),
        "commitments": sorted(of("commitment"), key=lambda r: (r["due"] or "9999", r["source"]["id"])),
        "contact_info": {"current": [r for r in contact if r["state"] == "current"],
                         "not_current": [r for r in contact if r["state"] != "current"]},
    }


def harvest_queue(client: AitoClient, company: str) -> dict:
    """What a Claude session reads to propose facts from an account's notes
    (docs/42). For each note, newest first: its body, whether it is thin, and the
    active facts already citing it; plus the account's other active facts, so a
    proposal doesn't restate them. Lookups only: nothing is ranked, guessed or
    written here (rules 1, 2). The session proposes, a person confirms, and
    add_fact writes.

    A held account isn't harvested (CRO): when the briefing's hold reads HOLD,
    unclear included, this returns the hold and no notes. That fails closed with
    the same reading as briefing."""
    requests: list[dict] = []

    def q(request: dict) -> list[dict]:
        requests.append(request)
        response = client.query(request)
        _whole(response, request["from"], request["limit"])
        return response["hits"]

    cid = _company_id(client, company)
    every = q({"from": "facts", "where": {"company_id": cid}, "limit": READ_LIMIT})
    active = [f for f in every if not f.get("superseded_by")]
    hold = _hold(every, active)["status"]
    out = {"company_id": cid, "hold": hold, "notes": [], "facts": [], "requests": requests}
    if hold and hold.startswith("HOLD"):
        return out
    docs = q({"from": "documents", "where": {"company_id": cid},
              "select": ["doc_id", "title", "noted_on", "updated", "body"], "limit": READ_LIMIT})
    docs.sort(key=lambda d: (d.get("noted_on") or "", d.get("updated") or "", d["doc_id"]), reverse=True)
    listed = {d["doc_id"] for d in docs}
    for d in docs:
        body = d.get("body") or ""
        out["notes"].append({
            "doc_id": d["doc_id"], "title": d["title"], "noted_on": d.get("noted_on"), "body": body,
            "thin": len(body) < schema.THIN_DOC_CHARS,
            "cited_by": sorted(f["fact_id"] for f in active
                               if f["source_kind"] == "doc" and f["source_id"] == d["doc_id"])})
    out["facts"] = [{k: f.get(k) for k in ("fact_id", "kind", "slot", "state", "statement",
                                           "valid_from", "source_kind", "source_id")}
                    for f in sorted(active, key=lambda f: (f["valid_from"], f["fact_id"]), reverse=True)
                    if not (f["source_kind"] == "doc" and f["source_id"] in listed)]
    return out
