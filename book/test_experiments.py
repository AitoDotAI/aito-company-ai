"""Learning-board gate: the Build-Measure-Learn loop. The seed plants the
Lean doctrine that small/cheap experiments validate more often than large
ones; the board (Aito's P(validated) by effort) should recover it. The
round-trip — start a bet, resolve it, see the rate move — is also exercised.
Requires a running Aito instance.
"""

import booktest as bt

from company_ai import experiments, loaders, log
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _print(t: bt.TestCaseRun, d: dict) -> None:
    t.tln(f"total={d['total']} decided={d['decided']} "
          f"validated_learning_rate={d['validated_learning_rate']} "
          f"favour_small={d['favour_small']}")
    t.tln(f"status_mix={d['status_mix']}")
    t.tln("by effort (does cheap validate more?):")
    for b in d["by_effort"]:
        t.tln(f"  {b['effort']:7} decided={b['decided']} validated={b['validated']} "
              f"observed={b['observed']} aito_p={b['aito_p']}")
    t.tln(f"running bets: {len(d['running'])}")


def test_board_seed(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_experiments(client, SEED_DIR)
    t.h1("Learning board, seed")
    d = experiments.board(client).derived
    _print(t, d)
    small = next(b for b in d["by_effort"] if b["effort"] == "small")
    large = next(b for b in d["by_effort"] if b["effort"] == "large")
    assert small["observed"] > large["observed"], \
        "the seed plants small > large validation; board should recover it"
    assert d["favour_small"], "board should flag the Lean doctrine"


def test_board_seed_tiny(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_experiments(client, SEED_TINY_DIR)
    t.h1("Learning board, tiny dataset (cold-start — honestly weak)")
    _print(t, experiments.board(client).derived)


def test_build_measure_learn_round_trip(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_experiments(client, SEED_DIR)

    t.h1("Build: start a running experiment")
    started = log.add_experiment(
        client, area="activation", type="onboarding",
        hypothesis="A guided first-run lifts trial_start_rate from 0.3 to 0.45.",
        metric="trial_start_rate", baseline=0.3, target=0.45, effort="small")
    t.tln(f"id prefix={started['experiment_id'].split('-')[0]} status={started['status']} "
          f"validated={started['validated']} result={started['result']}")
    assert started["status"] == "running" and started["validated"] is None

    t.h1("Learn: resolve it to a verdict")
    resolved = log.log_experiment_result(
        client, started["experiment_id"], status="validated", result=0.49,
        learning="guided first-run shipped")
    t.tln(f"status={resolved['status']} result={resolved['result']} "
          f"validated={resolved['validated']} decided set={bool(resolved['decided'])}")
    assert resolved["validated"] is True

    t.h1("a result without a terminal verdict is refused")
    try:
        log.log_experiment_result(client, started["experiment_id"],
                                  status="running", result=0.5)
        raise RuntimeError("accepted a non-terminal verdict")
    except AssertionError as e:
        t.tln(str(e))
