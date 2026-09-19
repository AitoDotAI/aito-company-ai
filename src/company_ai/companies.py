"""The company list — contacts rolled up by company, joined to their deals.

There is no accounts table: `company` is a denormalized string on both contacts
and deals (docs/03, docs/13). This is the read surface that treats it as one —
each distinct company with how many contacts it has, its furthest sales-funnel
stage, and any pipeline behind it. No prediction here: grouping and counting is
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

    co = q({"from": "companies", "where": {"company_id": company_id},
            "select": ["company_id", "name"], "limit": 1})
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
        "contacts": [{"id": c["contact_id"], "name": c["name"], "role": c.get("role"),
                      "segment": c.get("segment"), "tier": c.get("tier")} for c in contacts],
        "deals": [{"deal_id": d["deal_id"], "stage": d["stage"], "value_eur": d.get("value_eur"),
                   "probability": d.get("probability")} for d in deals],
        "documents": [{"doc_id": d["doc_id"], "title": d["title"], "kind": d.get("kind"),
                       "topics": d.get("topics"), "noted_on": d.get("noted_on")} for d in docs],
    }
    return result
