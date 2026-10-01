"""Every predictor learns only from finished rows (td-20260930191344950920 item 1).

An open deal, an unmeasured post, an open todo or a running experiment has no
outcome yet: its target column is null. The July-era v2 build read such nulls as
False (docs/24), and a derived column added to a populated table reads null for
old rows until a reload. Either way, rows that have not ended would teach
"lost / flop / not slipped / not accepted".

The test injects exactly those rows (unfinished, target False; a decision whose
derived `accepted` is stale) and asserts that every prediction is unchanged, to
the last digit. Then it deletes the finished history and asserts that each
predictor says so (no number) instead of failing or inventing a base rate.
"""

from datetime import date

import booktest as bt

from company_ai import decisions, deals, experiments, history, loaders, scorer, todos
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, Config

AS_OF = date(2026, 6, 14)
SLIP_KEY = ("sales", "high", "prep_needed")
# Engine v2.11.1: a nested `from` restricts single-feature evidence exactly, but
# with two features (here area & prep_status) part of the joint statistic is
# still counted over the whole table, so rows outside the population move P a
# little (0.5630 -> 0.5662 on the seed). Reported to core; listed, not hidden.
ENGINE_LEAK = {f"todos slip {'/'.join(SLIP_KEY)}"}


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient) -> None:
    loaders.create_schema(client)
    loaders.load_all(client, SEED_DIR)


def _predictions(client: AitoClient) -> dict:
    """every number the five predictors put on screen"""
    out = {}
    for blocker, champion in (("none", True), ("consultant_lock", False)):
        cl = deals.close_likelihood(client, "pilot", blocker, champion)
        out[f"deals p_win {blocker}/{champion}"] = (cl["p_win"], cl["basis"])
    s = scorer.score(client, "linkedin", {"format": "story"}).derived
    out["posts p_win linkedin/story"] = s["p_win"]
    out["posts base_p_win linkedin"] = s["base_p_win"]
    for lever in s["levers"]:
        out[f"posts lever {lever['field']}"] = [(o["value"], o["p"]) for o in lever["options"]]
    todo = dict(zip(("area", "priority", "prep_status"), SLIP_KEY))
    todos._annotate_slip_risk(client, todos.Result(), [todo])
    out[f"todos slip {'/'.join(SLIP_KEY)}"] = todo["slip_risk"] and todo["slip_risk"]["p"]
    for b in experiments.board(client).derived["by_effort"]:
        out[f"experiments aito_p {b['effort']}"] = b["aito_p"]
    for c in decisions.scorecard(client).derived["calibration"]:
        out[f"decisions aito_p {c['bucket']}"] = c["aito_p"]
    return out


def _copies(client: AitoClient, table: str, where: dict, n: int, id_col: str, **overrides) -> int:
    rows = client.query({"from": table, "where": where, "limit": n})["hits"]
    assert rows, f"the seed has no {table} matching {where}; the injection needs some"
    copies = [{**row, id_col: f"{row[id_col]}-coerced-{i}", **overrides}
              for i, row in enumerate(rows)]
    client.upload_batch(table, copies)
    return len(copies)


def _inject_unfinished_rows_read_as_false(client: AitoClient) -> dict:
    """the July data: rows with no outcome yet whose target reads False"""
    return {
        "open deals, won=False": _copies(
            client, "deals", {"stage": {"$or": ["lead", "qualified", "demo", "pilot", "negotiation"]}},
            40, "deal_id", won=False),
        "unmeasured posts, won=False": _copies(
            client, "posts", {"status": {"$or": ["planned", "go"]}}, 40, "post_id", won=False),
        "open todos, slipped=False": _copies(
            client, "todos", {"status": {"$or": ["ready", "prog", "blocked"]}}, 40, "todo_id",
            slipped=False),
        "running experiments, validated=False": _copies(
            client, "experiments", {"status": "running"}, 40, "experiment_id", validated=False),
        "accepted decisions, stale accepted=False": _stale_accepted(client),
    }


def _stale_accepted(client: AitoClient) -> int:
    """a decision is always decided; its risk is the derived `accepted` reading
    False while human_action says accepted (no rows added: the history is the same)"""
    where = {"human_action": "accepted"}
    n = client.query({"from": "decisions", "where": where, "limit": 0})["total"]
    client.update_entries("decisions", where, {"accepted": False})
    return n


def _print(t: bt.TestCaseRun, predictions: dict) -> None:
    for key, value in predictions.items():
        t.tln(f"  {key}: {value}")


def test_unfinished_rows_do_not_move_any_prediction(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    t.h1("Predictions on the seed")
    before = _predictions(client)
    _print(t, before)

    t.h1("Inject unfinished rows whose target reads False")
    for what, n in _inject_unfinished_rows_read_as_false(client).items():
        t.tln(f"  +{n} {what}")
    after = _predictions(client)

    t.h1("Predictions that moved (must be none)")
    moved = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    for key, (b, a) in moved.items():
        t.tln(f"  {key}: {b} -> {a}{'  (known engine leak)' if key in ENGINE_LEAK else ''}")
    if not moved:
        t.tln("  none")
    unexpected = sorted(set(moved) - ENGINE_LEAK)
    assert not unexpected, f"unfinished rows moved {len(unexpected)} predictions: {unexpected}"
    # the leak is the engine's; once it is fixed this fails, and ENGINE_LEAK is emptied
    fixed = sorted(ENGINE_LEAK - set(moved))
    assert not fixed, f"the engine leak no longer moves {fixed}: empty ENGINE_LEAK"


def test_no_finished_history_says_so(t: bt.TestCaseRun) -> None:
    client = _client()
    _load(client)
    for table, where in history.TERMINAL.items():
        ((field, condition),) = where.items()
        # _modify deletes on equalities only: one call per terminal value
        for value in condition["$or"] if isinstance(condition, dict) else [condition]:
            client.delete_entries(table, {field: value})
    t.h1("No finished rows in any table")
    predictions = _predictions(client)
    _print(t, predictions)
    numbers = {k: v for k, v in predictions.items()
               if v not in (None, [], (None, history.NO_HISTORY))}
    assert not numbers, f"predicted from no history: {numbers}"
