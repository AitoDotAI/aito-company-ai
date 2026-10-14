"""Load the engine kindly (td-20261014123607349120).

Core measured a 44 ms write turning into ~1 s when predict reads ran beside it.
The dashboard fired one close-likelihood request per deal profile, ~40 in
parallel, on every page load. Now:
  - all profiles go in one batch, answered from a shared cache that a deals or
    touches write invalidates;
  - one process sends at most INFERENCE_SLOTS inference calls at once, and one
    write at a time.
"""

import threading
import time

import booktest as bt
import requests

from company_ai import aito, deals, loaders, log
from company_ai.aito import TRACE, AitoClient
from company_ai.config import SEED_DIR, Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key, 120)


def _profiles(client: AitoClient) -> list[dict]:
    seen, out = set(), []
    for d in client.query({"from": "deals", "limit": 10000})["hits"]:
        if d.get("won") is not None:
            continue
        key = (d["stage"], d["blocker"], d["champion_present"], d["segment"])
        if key not in seen:
            seen.add(key)
            out.append({"stage": d["stage"], "blocker": d["blocker"],
                        "champion_present": d["champion_present"], "segment": d["segment"]})
    return sorted(out, key=lambda p: tuple(map(str, p.values())))


def _calls(fn) -> tuple[object, int]:
    trace: list = []
    token = TRACE.set(trace)
    try:
        return fn(), len(trace)
    finally:
        TRACE.reset(token)


def test_pwin_batch_is_cached_until_a_write(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    loaders.load_companies(client, SEED_DIR)
    loaders.load_deals(client, SEED_DIR)
    deals._pwin_cache.clear()
    profiles = _profiles(client)[:6]
    first, n1 = _calls(lambda: deals.pwin_many(client, profiles))
    single = [deals.close_likelihood(client, p["stage"], p["blocker"], p["champion_present"],
                                     segment=p["segment"])["p_win"] for p in profiles]
    t.h1(f"{len(profiles)} profiles in one batch")
    for p, r in zip(profiles, first):
        t.tln(f"  {p['stage']:11} {p['blocker']:16} champ={p['champion_present']!s:5} "
              f"{p['segment']:12} p_win={r['p_win']:.3f}")
    assert [r["p_win"] for r in first] == single, "the batch disagrees with single calls"
    again, n2 = _calls(lambda: deals.pwin_many(client, profiles))
    t.tln(f"Aito calls: first batch {n1}, same batch again {n2}")
    assert n2 == 0 and again == first
    open_id = client.query({"from": "deals", "where": {"stage": profiles[0]["stage"]},
                            "select": ["deal_id"], "limit": 1})["hits"][0]["deal_id"]
    log.log_deal_update(client, open_id, probability=55)
    _, n3 = _calls(lambda: deals.pwin_many(client, profiles))
    t.tln(f"after a deal update: {n3} calls (recomputed)")
    assert n3 > 0


class _Slow:
    status_code, text, content = 200, "", b"{}"

    def json(self):
        return {"hits": []}


def test_at_most_two_inference_calls_at_once(t: bt.TestCaseRun) -> None:
    live, peak = [0], [0]
    lock = threading.Lock()
    real = requests.request

    def slow(method, url, **kw):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return _Slow()
    requests.request = slow
    try:
        c = AitoClient("http://aito.invalid/db/x")
        for label, path, body in (("predict", "/api/v2/_predict", {"from": "t"}),
                                  ("write", "/api/v2/data/t/batch", [{}])):
            live[0] = peak[0] = 0
            threads = [threading.Thread(target=c._request, args=("POST", path, body))
                       for _ in range(8)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            t.tln(f"8 concurrent {label} calls -> at most {peak[0]} in flight")
            assert peak[0] == (aito.INFERENCE_SLOTS if label == "predict" else 1)
    finally:
        requests.request = real
