"""The company list — contacts rolled up by company, joined to their deals.

Each distinct company with how many contacts it has, its furthest
sales-funnel stage, and any pipeline behind it. The `companies` table (the
knowledge graph's hub, docs/31) holds each account's harvested facts;
`detail` returns them with the linked contacts, deals and notes. No prediction here: grouping and counting is
formatting (rule 2 governs *predictive* logic, which this isn't). The Sales
dashboard renders it as the Companies tab; the agent reads the same via MCP.
"""

from dataclasses import dataclass, field

from . import schema
from .aito import AitoClient


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


# furthest sales-funnel stage a contact has reached, from the load-time derived
# booleans on contacts (docs/09). Ordered coldest → warmest; the label is what
# the company row shows.
_STAGE_ORDER = [
    ("ever_meeting", "meeting"),
    ("ever_conversation", "conversation"),
    ("ever_reached", "reached"),
    ("ever_touched", "touched"),
]


def _contact_stage_rank(contact: dict) -> int:
    """Higher = warmer. 0 means not yet touched."""
    for i, (flag, _label) in enumerate(_STAGE_ORDER):
        if contact.get(flag):
            return len(_STAGE_ORDER) - i
    return 0


def _rank_label(rank: int) -> str:
    if rank == 0:
        return "—"
    return _STAGE_ORDER[len(_STAGE_ORDER) - rank][1]


def _mode(values: list) -> str | None:
    """Most common value (ties broken by first-seen), or None if empty."""
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: (counts[k], k), default=None) if counts else None


def roster(client: AitoClient, limit: int = 500) -> Result:
    """Every company (from contacts and deals), each with its contact count, the
    furthest funnel stage any of its contacts reached, and its deal footprint:
    total deals, open deals, and open pipeline value. Sorted by open pipeline
    value (companies with live money first), then contact count, then name."""
    result = Result()
    creq = {"from": "contacts", "limit": 100000}
    dreq = {"from": "deals", "limit": 100000}
    contacts = client.query(creq)["hits"]
    deals = client.query(dreq)["hits"]
    result.calls.append(("_query", creq, {"total": len(contacts)}))
    result.calls.append(("_query", dreq, {"total": len(deals)}))

    by_company: dict[str, dict] = {}

    def slot(company: str) -> dict:
        return by_company.setdefault(company, {
            "company": company, "contacts": 0, "segments": [], "stage_rank": 0,
            "deals": 0, "open_deals": 0, "pipeline_eur": 0, "won": False,
        })

    for c in contacts:
        s = slot(c["company"])
        s["contacts"] += 1
        s["segments"].append(c["segment"])
        s["stage_rank"] = max(s["stage_rank"], _contact_stage_rank(c))

    for d in deals:
        s = slot(d["company"])
        s["deals"] += 1
        if d["stage"] in schema.DEAL_OPEN_STAGES:
            s["open_deals"] += 1
            s["pipeline_eur"] += d["value_eur"]
        if d["stage"] == "closed_won":
            s["won"] = True
        # a company known only through a deal has no contacts; still list it
        if d["segment"] and not s["segments"]:
            s["segments"].append(d["segment"])

    from .loaders import company_slug
    companies = [
        {
            "company": s["company"],
            "company_id": company_slug(s["company"]),   # the graph id, for drill-in
            "contacts": s["contacts"],
            "segment": _mode(s["segments"]),
            "stage": _rank_label(s["stage_rank"]),
            "deals": s["deals"],
            "open_deals": s["open_deals"],
            "pipeline_eur": s["pipeline_eur"],
            "won": s["won"],
        }
        for s in by_company.values()
    ]
    companies.sort(key=lambda r: (-r["pipeline_eur"], -r["contacts"], r["company"]))
    result.derived = {"count": len(companies), "companies": companies[:limit]}
    return result


def detail(client: AitoClient, company_id: str) -> Result:
    """One company node: its name plus the contacts, deals, and notes that link to
    it via `company_id` (the entity graph, .ai/tasks/15) — the drill-in behind the
    Companies list, so a company opens to show its people and its notes. Grouping/
    formatting over three link queries, no prediction (rule 2)."""
    result = Result()

    def q(request):
        response = client.query(request)
        result.calls.append(("_query", request, response))
        return response["hits"]

    from .graph import COMPANY_FACTS
    co = q({"from": "companies", "where": {"company_id": company_id},
            "select": ["company_id", "name", *COMPANY_FACTS], "limit": 1})
    name = co[0]["name"] if co else company_id
    contacts = q({"from": "contacts", "where": {"company_id": company_id},
                  "select": ["contact_id", "name", "role", "segment", "tier"], "limit": 10000})
    deals = q({"from": "deals", "where": {"company_id": company_id},
               "select": ["deal_id", "stage", "value_eur", "probability"], "limit": 10000})
    docs = q({"from": "documents", "where": {"company_id": company_id},
              "select": ["doc_id", "title", "kind", "topics", "noted_on", "updated"], "limit": 10000})
    docs.sort(key=lambda d: (d.get("noted_on") or "", d.get("updated") or "", d["doc_id"]),
              reverse=True)
    result.derived = {
        "company_id": company_id, "name": name,
        # the node's harvested facts (docs/31); None when the company row is missing
        "facts": {k: co[0].get(k) for k in COMPANY_FACTS} if co else None,
        "contacts": [{"id": c["contact_id"], "name": c["name"], "role": c.get("role"),
                      "segment": c.get("segment"), "tier": c.get("tier")} for c in contacts],
        "deals": [{"deal_id": d["deal_id"], "stage": d["stage"], "value_eur": d.get("value_eur"),
                   "probability": d.get("probability")} for d in deals],
        "documents": [{"doc_id": d["doc_id"], "title": d["title"], "kind": d.get("kind"),
                       "topics": d.get("topics"), "noted_on": d.get("noted_on")} for d in docs],
    }
    return result


BRIEFING_TOUCHES = 10    # the latest touches and notes a briefing shows (one screen)
BRIEFING_NOTES = 10
_CLOSED_TODO = {"done", "archived"}


def _source(kind: str, id_: str, date) -> dict:
    return {"kind": kind, "id": id_, "date": str(date) if date is not None else None}


def _resolve(client: AitoClient, company: str, result: Result) -> dict:
    """A company by its company_id, else by its exact name. Unknown raises:
    an empty briefing would read as an account with nothing going on."""
    for where in ({"company_id": company}, {"name": company}):
        request = {"from": "companies", "where": where, "limit": 2}
        response = client.query(request)
        result.calls.append(("_query", request, response))
        if response["hits"]:
            assert len(response["hits"]) == 1, f"{where} matches {len(response['hits'])} companies"
            return response["hits"][0]
    raise LookupError(f"no company with company_id or name {company!r}")


def briefing(client: AitoClient, company: str) -> Result:
    """The current state of one account in one read (td-20261103224048158692,
    slice 1): the company row, its open deals with their recorded next step,
    the latest touches and notes, the open todos linked to it, and its
    stakeholders. Every fact carries `source` (kind, id, date) so an agent can
    open it; nothing is inferred or summarised. Grouping, sorting and
    formatting over link queries, no prediction (rule 2). Works for an account
    with no deal row. `company` is a company_id or the exact name."""
    result = Result()

    def q(request):
        response = client.query(request)
        result.calls.append(("_query", request, response))
        return response["hits"]

    co = _resolve(client, company, result)
    cid = co["company_id"]
    contacts = q({"from": "contacts", "where": {"company_id": cid},
                  "select": ["contact_id", "name", "role", "tier", "segment"], "limit": 10000})
    names = {c["contact_id"]: c["name"] for c in contacts}
    deals = q({"from": "deals", "where": {"company_id": cid}, "limit": 10000})
    for d in deals:
        assert d["stage"] in schema.DEAL_STAGES, f"unknown deal stage: {d}"
    deal_ids = {d["deal_id"] for d in deals}

    who = [{"company_id": cid}, *({"contact_id": k} for k in names)]
    touches = q({"from": "touches", "where": {"$or": who}, "orderBy": {"$desc": "ts"},
                 "limit": 10000})
    last_touch: dict[str, dict] = {}
    for x in touches:           # newest first, so the first per contact is its latest
        last_touch.setdefault(x["contact_id"], x)

    linked = [*({"linked_type": "deal", "linked_id": k} for k in deal_ids),
              *({"linked_type": "contact", "linked_id": k} for k in names),
              *({"stakeholder_id": k} for k in names)]
    todos = q({"from": "todos", "where": {"$or": linked}, "limit": 10000}) if linked else []
    for x in todos:
        assert x["status"] in schema.TODO_STATUS, f"unknown todo status: {x}"
    todos = sorted((x for x in todos if x["status"] not in _CLOSED_TODO),
                   key=lambda x: (x["priority"], x.get("due_date") or "9999", x["todo_id"]))
    docs = q({"from": "documents", "where": {"company_id": cid},
              "select": ["doc_id", "title", "kind", "topics", "noted_on", "updated", "stakeholder_id"],
              "limit": 10000})
    docs.sort(key=lambda d: (d.get("noted_on") or "", d.get("updated") or "", d["doc_id"]), reverse=True)

    def todo_row(x):
        link = (f"{x['linked_type']}:{x['linked_id']}" if x.get("linked_type") else None) \
            or (f"stakeholder:{x['stakeholder_id']}" if x.get("stakeholder_id") else None)
        return {"title": x["title"], "status": x["status"], "priority": x["priority"],
                "due_date": x.get("due_date"), "linked": link,
                "source": _source("todo", x["todo_id"], x.get("due_date"))}

    def next_step(deal_id):
        # the latest touch on this deal that recorded a next action, as written
        for x in touches:
            if x.get("deal_id") == deal_id and x.get("next_action"):
                return {"text": x["next_action"], "due": x.get("next_action_due"),
                        "source": _source("touch", x["touch_id"], x["ts"])}
        return None

    open_deals = sorted((d for d in deals if d["stage"] in schema.DEAL_OPEN_STAGES),
                        key=lambda d: (d.get("last_touch_date") or d.get("created") or "", d["deal_id"]),
                        reverse=True)
    result.derived = {
        "company": {"name": co["name"], **{k: co.get(k) for k in COMPANY_ROW_FIELDS},
                    "source": _source("company", cid, None)},
        "open_deals": [{"deal_id": d["deal_id"], "stage": d["stage"], "value_eur": d.get("value_eur"),
                        "probability": d.get("probability"), "blocker": d.get("blocker"),
                        "next_step": next_step(d["deal_id"]),
                        "todos": [todo_row(x) for x in todos
                                  if x.get("linked_type") == "deal" and x.get("linked_id") == d["deal_id"]],
                        "source": _source("deal", d["deal_id"], d.get("last_touch_date") or d.get("created"))}
                       for d in open_deals],
        "closed_deals": len(deals) - len(open_deals),
        "stakeholders": [{"contact_id": c["contact_id"], "name": c["name"], "role": c.get("role"),
                          "tier": c.get("tier"),
                          "last_touch": (_source("touch", last_touch[c["contact_id"]]["touch_id"],
                                                 last_touch[c["contact_id"]]["ts"])
                                         if c["contact_id"] in last_touch else None),
                          "source": _source("contact", c["contact_id"], None)}
                         for c in sorted(contacts, key=lambda c: c["name"])],
        "touches": [{"contact": names.get(x["contact_id"], x["contact_id"]), "channel": x["channel"],
                     "direction": x.get("direction"), "outcome": x["outcome"],
                     "next_action": x.get("next_action"), "next_action_due": x.get("next_action_due"),
                     "notes": x.get("notes"), "deal_id": x.get("deal_id"),
                     "source": _source("touch", x["touch_id"], x["ts"])}
                    for x in touches[:BRIEFING_TOUCHES]],
        "touches_total": len(touches),
        "notes": [{"title": d["title"], "kind": d.get("kind"), "topics": d.get("topics"),
                   "stakeholder_id": d.get("stakeholder_id"),
                   "source": _source("document", d["doc_id"], d.get("noted_on"))}
                  for d in docs[:BRIEFING_NOTES]],
        "notes_total": len(docs),
        "todos": [todo_row(x) for x in todos],
    }
    return result


COMPANY_ROW_FIELDS = ["industry", "relationship", "country", "mrr_eur", "technical_contact"]
