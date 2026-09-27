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
        "classify-account",
        "What kind of company is this, judged only by who works there?",
        # Node classification: infer an attribute OF THE ACCOUNT from the set of
        # people linked to it. The account's own industry column is not read —
        # the evidence is the neighbourhood, reached backwards through
        # $refs.contacts.company_id. This is the shape a graph is for, and it is
        # the one card here with no relational equivalent.
        {"from": "companies",
         "where": {"$refs.contacts.company_id": {"$exists": {"role": "CFO"}}},
         "predict": "industry", "select": ["$value", "$p"], "limit": 5},
    ),
    (
        "explained-odds",
        "An accounting account, a champion on board, nothing blocking — what are the odds?",
        # Several facts at once, one of them reached across the link: the
        # account's industry lives on the company, the champion and the blocker
        # on the deal. $why returns what each of them did to the number, so the
        # answer arrives with its reasons instead of as a bare probability.
        {"from": "deals",
         "where": {"company_id.industry": "accounting",
                   "champion_present": True,
                   "blocker": "none"},
         "predict": "won", "select": ["$value", "$p", "$why"]},
    ),
    (
        "cto-odds",
        "At an account where we know a CTO, how likely is a deal to close?",
        # The one card here that a relational database could not also produce.
        # It walks the link FORWARD from the deal to its account, then BACKWARDS
        # to that account's contacts, and asks whether any of them is a CTO —
        # a fact that exists nowhere on the deal. The view puts the answer next
        # to BASELINE_REQUEST below, because a conditioned probability only
        # means something against the unconditioned one.
        {"from": "deals",
         "where": {"company_id.$refs.contacts.company_id":
                   {"$exists": {"role": "CTO"}}},
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
        "Which accounts have a CTO on file?",
        # reverse hop: a company's set of contacts, filtered by $exists
        {"from": "companies",
         "where": {"$refs.contacts.company_id": {"$exists": {"role": "CTO"}}},
         "select": ["name", "industry", "relationship"], "limit": 6},
    ),
    (
        "finance-at-prospects",
        "Which CFOs work at accounts we are still selling to?",
        {"from": "contacts",
         "where": {"role": "CFO", "company_id.relationship": "prospect"},
         "select": ["name", "company", "country"], "limit": 6},
    ),
    (
        "accounting-deals",
        "What is in play across the accounting industry?",
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
]



# The same prediction with NO condition. Quoting a conditioned probability
# without this is how "50%" once got reported as a finding when the base rate
# was 25% — and how a 27% result can look decisive at 73/27 while saying
# nothing. Computed, never written down: every time these numbers were typed
# into prose they drifted the next time the seed was regenerated.
BASELINE_REQUEST = {"from": "deals", "predict": "won", "select": ["$value", "$p"]}


def _p_true(hits: list[dict]) -> float | None:
    """P(won = true) out of a predict response."""
    hit = next((h for h in hits if h.get("$value") in (True, "true")), None)
    return hit["$p"] if hit else None


def answer(client: AitoClient, question_id: str, prose: str, request: dict) -> dict:
    """Run one question. A failure is reported, not swallowed: this is a
    deliberately un-battle-tested corner of Aito, and a card that says which
    query broke and how is worth more than a view that refuses to render."""
    out = {"id": question_id, "question": prose, "request": request}
    try:
        response = client.query(request)
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
    except Exception as exc:                      # noqa: BLE001 — reported, see above
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def board(client: AitoClient) -> dict:
    """Every question, each with the query that answered it."""
    answers = [answer(client, qid, prose, req) for qid, prose, req in QUESTIONS]
    base = answer(client, "baseline", "How likely is any deal to close?", BASELINE_REQUEST)
    conditioned = next((a for a in answers if a["id"] == "cto-odds"), None)
    return {
        "answers": answers,
        # the lift, for the view to state honestly: both sides measured, neither
        # written down.
        "baseline_p": _p_true(base.get("hits", [])),
        "conditioned_p": _p_true((conditioned or {}).get("hits", [])),
        "ok": sum(1 for a in answers if "error" not in a),
        "failed": [a["id"] for a in answers if "error" in a],
    }
