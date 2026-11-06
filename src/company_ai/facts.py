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
ROLE_ORDER = ("champion", "decision_owner", "sponsor", "other")


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
    rows = client.query({"from": "facts", "where": where, "limit": 10000})["hits"]
    if active_only:
        rows = [r for r in rows if not r.get("superseded_by")]
    return sorted(rows, key=lambda r: (r["valid_from"], r["fact_id"]), reverse=True)


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
        "conflicts": conflicts,
        "decisions": of("decision"),
        "open_questions": of("open_question"),
        "commitments": sorted(of("commitment"), key=lambda r: (r["due"] or "9999", r["source"]["id"])),
        "contact_info": {"current": [r for r in contact if r["state"] == "current"],
                         "not_current": [r for r in contact if r["state"] != "current"]},
    }
