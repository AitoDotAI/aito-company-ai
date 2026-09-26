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

from .aito import AitoClient

# Each question is (id, prose, request). The prose is the question a person
# actually asks; the request is what the graph makes of it. The view shows
# both, because the point of the demo is that they are close together.
QUESTIONS: list[tuple[str, str, dict]] = [
    (
        "paying",
        "Who actually pays us, and how much?",
        {"from": "companies", "where": {"relationship": "customer"},
         "orderBy": {"$desc": "mrr_eur"},
         "select": ["name", "industry", "country", "mrr_eur"], "limit": 6},
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
        "finance-at-prospects",
        "Which CFOs work at accounts we are still selling to?",
        {"from": "contacts",
         "where": {"role": "CFO", "company_id.relationship": "prospect"},
         "select": ["name", "company", "country"], "limit": 6},
    ),
    (
        "accounts-with-cto",
        "Which accounts have a CTO on file?",
        # reverse hop: a company's set of contacts, filtered by $exists
        {"from": "companies",
         "where": {"$refs.contacts.company_id": {"$exists": {"role": "CTO"}}},
         "select": ["name", "industry", "relationship"], "limit": 6},
    ),
    (
        "accounting-deals",
        "What is in play across the accounting industry?",
        # forward hop from a deal to its account's harvested industry
        {"from": "deals", "where": {"company_id.industry": "accounting"},
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
    (
        "predict-by-industry",
        "In accounting, how likely is a deal to be won?",
        # the layer above lookup: condition a prediction on a fact that lives
        # on the OTHER side of the link, and let Aito answer with a calibrated
        # probability rather than a count.
        {"from": "deals", "where": {"company_id.industry": "accounting"},
         "predict": "won", "select": ["$value", "$p"]},
    ),
]


def answer(client: AitoClient, question_id: str, prose: str, request: dict) -> dict:
    """Run one question. A failure is reported, not swallowed: this is a
    deliberately un-battle-tested corner of Aito, and a card that says which
    query broke and how is worth more than a view that refuses to render."""
    out = {"id": question_id, "question": prose, "request": request}
    try:
        response = client.query(request)
        out["hits"] = response.get("hits", [])
        out["total"] = response.get("total")
    except Exception as exc:                      # noqa: BLE001 — reported, see above
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def board(client: AitoClient) -> dict:
    """Every question, each with the query that answered it."""
    answers = [answer(client, qid, prose, req) for qid, prose, req in QUESTIONS]
    return {
        "answers": answers,
        "ok": sum(1 for a in answers if "error" not in a),
        "failed": [a["id"] for a in answers if "error" in a],
    }
