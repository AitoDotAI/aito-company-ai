"""The finished rows each predictor learns from, as a nested `from`.

A prediction learns an outcome, so it must learn only from rows whose outcome
is known: closed deals, measured posts, done todos, decided experiments and
decisions. Every target column is a nullable Boolean derived at load, null
while the row is open. An open row that reads False instead (the July-era v2
build coerced null to False, docs/24; a derived column added to a populated
table) would teach "lost / flop / not slipped" from rows that have not ended.
The terminal state is read from the row's own lifecycle field (stage, status,
outcome, human_action), never from the target.

`{"from": {"from": T, "where": TERMINAL[T]}, ...}` restricts the population
the engine counts over. Unlike the same filter as outer `where` evidence, it is
not a soft condition the model can weigh, and it never shows up in the `$why`.

An empty population is a 400 from the engine ("nested from: the restriction
matched no rows"). That is a real state, a company with no finished history yet,
so `predict` returns None for it and callers say "not enough history" (rule 3:
no silent fallback number). Any other error still raises.
"""

from . import schema
from .aito import AitoClient, AitoError

TERMINAL: dict[str, dict] = {
    "deals": {"stage": {"$or": sorted(schema.DEAL_CLOSED_STAGES)}},
    "posts": {"outcome": {"$or": sorted(schema.POST_OUTCOMES)}},
    "todos": {"status": "done"},
    "experiments": {"status": {"$or": sorted(schema.EXPERIMENT_TERMINAL)}},
    "decisions": {"human_action": {"$or": sorted(schema.HUMAN_ACTIONS)}},
}

NO_HISTORY = "no_history"


def finished(table: str) -> dict:
    """the nested `from` over the table's finished rows"""
    return {"from": table, "where": TERMINAL[table]}


def is_empty_population(error: AitoError) -> bool:
    """Was this 400 the engine saying "no finished rows to learn from yet"?

    Recognised by the structured code where the engine sends one (2.11.4+:
    `query.empty_population`), and by the message on builds that predate it.
    Matching the message alone broke on 2.11.4, which reworded it ("the
    population is empty — no row of 'deals' matches…"): a company with no
    closed deals got an error where it should have got "not enough history"."""
    text = str(error)
    return "-> 400" in text and (
        "query.empty_population" in text      # 2.11.4+: the code, stable
        or "matched no rows" in text)          # earlier builds: the message


def predict(client: AitoClient, request: dict) -> dict | None:
    """client.predict, or None when the nested population is empty"""
    try:
        return client.predict(request)
    except AitoError as error:
        if is_empty_population(error):
            return None
        raise


def recommend(client: AitoClient, request: dict) -> dict | None:
    """client.recommend, or None when the nested population is empty"""
    try:
        return client.recommend(request)
    except AitoError as error:
        if is_empty_population(error):
            return None
        raise


def count(client: AitoClient, table: str, where: dict | None = None) -> tuple[dict, dict]:
    """(request, response) counting finished rows matching `where`. Counting is
    a `_query`, so an empty population is a total of 0, not an error."""
    request = {"from": table, "limit": 0,
               "where": {"$and": [TERMINAL[table], where]} if where else TERMINAL[table]}
    return request, client.query(request)
