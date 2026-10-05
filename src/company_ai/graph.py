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
    answers = [answer(client, qid, prose, req) for qid, prose, req in questions(client)]
    # the base rate is a card too: the view quotes it, so its query is on the page
    base = answer(client, "baseline", "How likely is any closed deal to have been won?",
                  BASELINE_REQUEST)
    answers.append(base)
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
