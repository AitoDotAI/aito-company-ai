"""Aito-suggested todo fields — Pass 2 of the action surface (docs/12).

When the operator types a todo title, Aito predicts the blank *classifying*
fields — `area` and `action_type` — from the title's words (`_predict` with a
`$match` on the analyzed title). These are suggestions with their calibrated
$p; the operator confirms or overrides before saving. Honest cold start: on
thin todo history the $p is low and the top pick may be wrong — shown as-is,
never auto-applied.

The stakeholder suggestion is a *literal mention scan*, not a prediction — if
a known contact's name or company token appears in the title, that contact is
offered. It is labelled separately so it is never mistaken for an Aito
prediction (rule 2 owns prediction; this is a lookup/join in Python).
"""

import re
from dataclasses import dataclass, field

from .aito import AitoClient

# company-suffix and filler tokens that shouldn't trigger a stakeholder match
_STOP = {"oy", "ab", "ou", "oü", "gmbh", "inc", "ltd", "plc", "the", "before",
         "with", "call", "email", "to", "for", "and", "of"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\wäöåüÄÖÅÜ]+", (text or "").lower())
            if len(t) >= 3 and t not in _STOP}


@dataclass
class Result:
    calls: list = field(default_factory=list)
    derived: dict | None = None


def _predict_field(client: AitoClient, result: Result, title: str, target: str,
                   k: int = 3) -> list[dict]:
    """Aito's ranked values for `target` given the title's words. A predict
    failure (e.g. empty table) yields no suggestion — advisory, not a data
    path — rather than blocking the editor."""
    request = {"from": "todos", "where": {"title": {"$match": title}},
               "predict": target, "select": ["$p", "$value"], "limit": k}
    try:
        response = client.predict(request)
    except Exception:
        return []
    result.calls.append(("_predict", request, response))
    return [{"value": h["$value"], "p": h["$p"]} for h in response.get("hits", [])
            if h.get("$value") is not None]


def _mention_scan(client: AitoClient, result: Result, title: str) -> list[dict]:
    """Contacts whose name or company token literally appears in the title.
    A lookup, not a ranking."""
    request = {"from": "contacts", "limit": 100000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    title_tokens = _tokens(title)
    if not title_tokens:
        return []
    hits = []
    for c in response["hits"]:
        matched = (_tokens(c["name"]) | _tokens(c["company"])) & title_tokens
        if matched:
            hits.append({"id": c["contact_id"], "name": c["name"],
                         "company": c["company"], "matched": sorted(matched)})
    return hits


def classify_todo(client: AitoClient, title: str, given: dict | None = None) -> Result:
    """Suggest the blank fields for a todo title. `given` is the fields the
    operator already filled (those are left alone). Returns area/action_type
    predictions (with $p) and candidate stakeholders (literal matches)."""
    given = given or {}
    result = Result()
    suggest = {}
    for target in ("area", "action_type"):
        if given.get(target):
            continue
        ranked = _predict_field(client, result, title, target)
        if ranked:
            suggest[target] = {"top": ranked[0], "alts": ranked[1:]}
    stakeholders = ([] if given.get("stakeholder_id")
                    else _mention_scan(client, result, title))
    result.derived = {"title": title, "suggest": suggest, "stakeholders": stakeholders}
    return result


# ---- note (document) inference (docs/25) ----

def _company_scan(client: AitoClient, result: Result, title: str) -> list[dict]:
    """Companies (the entity) whose name token literally appears in the title.
    A lookup against the graph node, not a ranking."""
    request = {"from": "companies", "limit": 100000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    title_tokens = _tokens(title)
    if not title_tokens:
        return []
    out = []
    for c in response["hits"]:
        matched = _tokens(c["name"]) & title_tokens
        if matched:
            out.append({"company_id": c["company_id"], "name": c["name"],
                        "matched": sorted(matched)})
    return out


def _contacts_at(client: AitoClient, result: Result, company_ids: list[str]) -> list[dict]:
    """The contacts at the given companies, via the `company_id` link — the graph
    surfacing the people to attach a note to (e.g. Robin at Acme)."""
    if not company_ids:
        return []
    request = {"from": "contacts", "where": {"company_id": {"$or": sorted(set(company_ids))}},
               "select": ["contact_id", "name", "role", "company"], "limit": 10000}
    response = client.query(request)
    result.calls.append(("_query", request, response))
    return [{"id": h["contact_id"], "name": h["name"], "role": h.get("role"),
             "company": h.get("company")} for h in response["hits"]]


def _topic_suggest(client: AitoClient, result: Result, title: str) -> list[str]:
    """Existing topics whose word appears in the title — a lookup against the
    store's topic index (not a prediction), so a "meeting note" surfaces the
    `meeting` topic if others already use it."""
    from . import documents
    title_tokens = _tokens(title)
    if not title_tokens:
        return []
    idx = documents.topics(client)
    result.calls.extend(idx.calls)
    return [it["topic"] for it in idx.derived["topics"]
            if _tokens(it["topic"]) & title_tokens]


def classify_document(client: AitoClient, title: str, given: dict | None = None) -> Result:
    """Infer a note's fields from its title, Aito-side (rule 2): mention-scan the
    companies named in the title, surface those companies' contacts via the
    `company_id` link, plus any contact named directly, and suggest existing
    topics whose word appears. All lookups + a graph traversal — no Python
    ranking or prediction of a number. The operator confirms before saving."""
    given = given or {}
    result = Result()
    companies = [] if given.get("company") else _company_scan(client, result, title)
    named = [] if given.get("stakeholder_id") else _mention_scan(client, result, title)
    at_co = _contacts_at(client, result, [c["company_id"] for c in companies])
    seen, contacts = set(), []
    for c in named + at_co:
        cid = c.get("id")
        if cid and cid not in seen:
            seen.add(cid)
            contacts.append({"id": cid, "name": c["name"], "role": c.get("role"),
                             "company": c.get("company")})
    topics = [] if given.get("topics") else _topic_suggest(client, result, title)
    result.derived = {"title": title, "companies": companies,
                      "contacts": contacts, "topics": topics}
    return result


def document_context(client: AitoClient, title: str, company: str | None = None,
                     top_n: int = 5) -> Result:
    """Prior notes related to a new one, for grounding (rule 2: Aito text-search +
    a company filter, no re-ranking in Python). `similar` = smart-search hits on
    the title; `same_company` = the company's other notes (newest first)."""
    from . import documents, search
    result = Result()
    similar = []
    try:
        s = search.search(client, title, kind="doc", top_n=top_n)
        result.calls.extend(s.calls)
        similar = [{"title": h.get("title"), "source_id": h.get("source_id")}
                   for h in s.derived["hits"]]
    except Exception:
        similar = []   # search advisory-only; never block the editor
    same_company = []
    if company:
        docs = documents.feed(client, company=company).derived["documents"]
        same_company = [{"doc_id": d["doc_id"], "title": d["title"],
                         "noted_on": d.get("noted_on")} for d in docs[:top_n]]
    result.derived = {"similar": similar, "same_company": same_company}
    return result
