"""Post scorer gate: the messaging-formula data layer on both datasets.

Snapshots P(win), the channel base rate, the per-feature $why, and the
lever recommendations for several drafts. The contrast between a
doctrine-aligned draft (narrate, first-comment, manual) and its opposite
(announce, body link, AI) is the dogfood evidence; the snapshot pins it.
Requires a running Aito instance.
"""

import json

import booktest as bt

from company_ai import loaders, scorer
from company_ai.aito import AitoClient
from company_ai.config import SEED_DIR, SEED_TINY_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def _load(client: AitoClient, data_dir) -> None:
    loaders.create_schema(client)
    loaders.load_materials(client, data_dir)  # posts denormalize from these
    loaders.load_channels(client, data_dir)
    loaders.load_posts(client, data_dir)


def _print(t: bt.TestCaseRun, channel: str, features: dict) -> None:
    result = scorer.score(_client(), channel, features)
    d = result.derived
    t.h2(f"{channel}: {json.dumps(features, sort_keys=True)}")
    for endpoint, request, _ in result.calls:
        t.tln(f"  {endpoint}: {json.dumps(request, sort_keys=True)}")
    t.tln(f"  P(win)={d['p_win']:.4f}  base={d['base_p_win']:.4f}")
    for w in d["why"]:
        t.tln(f"    why {w['label']}  lift={w['lift']:.4f}")
    for lv in d["levers"]:
        opts = ", ".join(f"{o['value']}={o['p']:.4f}" for o in lv["options"])
        flag = " (SWITCH)" if lv["actionable"] else ""
        t.tln(f"    lever {lv['field']}: best={lv['best']}{flag}  [{opts}]")


def test_scorer_seed(t: bt.TestCaseRun) -> None:
    _load(_client(), SEED_DIR)
    t.h1("Doctrine-aligned LinkedIn draft (narrate, first comment, manual)")
    _print(t, "linkedin", {"tone": "narrate", "link_placement": "comment",
                           "ai_made": "manual", "weekday": "wed", "lane": "warm"})
    t.h1("Its opposite (announce, body link, AI) — should crater")
    _print(t, "linkedin", {"tone": "announce", "link_placement": "body",
                           "ai_made": "ai", "weekday": "mon", "lane": "warm"})
    t.h1("Hacker News show-hn draft")
    _print(t, "hackernews", {"tone": "builder", "format": "show-hn", "ai_made": "manual"})


def test_scorer_seed_tiny(t: bt.TestCaseRun) -> None:
    _load(_client(), SEED_TINY_DIR)
    t.h1("Scorer on the tiny dataset (cold-start honesty)")
    _print(t, "linkedin", {"tone": "narrate", "link_placement": "comment"})


def test_unknown_channel_and_feature_assert(t: bt.TestCaseRun) -> None:
    t.h1("Unknown channel and unknown feature both raise")
    for label, fn in {
        "unknown channel": lambda: scorer.score(_client(), "tiktok", {}),
        "unknown feature": lambda: scorer.score(_client(), "linkedin", {"mood": "spicy"}),
    }.items():
        try:
            fn()
            raise RuntimeError(f"{label}: was accepted")
        except AssertionError as e:
            t.tln(f"{label}: {e}")
