"""A book that deletes or reseeds refuses any instance that isn't a dedicated
test env, before its first call (CPO review of #93, 8.11.2026).

The suite-wide guard in book/__booktest__.py already pins every run to
.env.test and refuses an unmarked instance. This is the same rule, applied
again where a book takes its client, so a book function called any other way
(imported into a script, run from a REPL with COMPANY_AI_ENV=.env.aito) can't
drop the change log on the ops instance either. One rule, two places:
config.is_test_instance."""

import booktest as bt

from book._target import guarded_client
from company_ai.config import is_test_instance


class Recording:
    """Stands in for AitoClient: records every call, so the book can show none happened."""

    calls: list = []

    def __init__(self, url, key, *a, **k):
        Recording.calls.append(("connect", url))


def test_an_instance_not_marked_as_a_test_env_is_refused_before_any_call(t: bt.TestCaseRun) -> None:
    t.h1("is_test_instance")
    accepted = ("https://shared.aito.ai/db/x/env/booktest", "https://shared.aito.ai/db/x/env/test",
                "https://test.aito.app", "https://test-company-ai.aito.app")
    # the near-misses a substring match let through (CPO review of #93)
    refused = ("https://internal.aito.ai/db/aito", "https://aito-company-ai.aito.app",
               "http://localhost:9005", "https://latest.aito.ai/db/aito",
               "https://contest-db.aito.app", "https://aito-test.aito.app",
               "https://shared.aito.ai/db/x/env/test-prod", "https://shared.aito.ai/db/x/env/testdrive",
               "https://internal.aito.ai/db/aito?x=/env/test", "https://internal.aito.ai/db/aito#/env/booktest")
    for url in accepted + refused:
        t.tln(f"  {url}: {is_test_instance(url)}")
    assert all(is_test_instance(u) for u in accepted), [u for u in accepted if not is_test_instance(u)]
    assert not any(is_test_instance(u) for u in refused), [u for u in refused if is_test_instance(u)]

    t.h1("guarded_client() pointed at the ops instance")
    Recording.calls = []
    try:
        guarded_client(url="https://internal.aito.ai/db/aito", key="k", client_class=Recording)
    except AssertionError as e:
        t.tln(f"  refused: {e}")
    else:
        raise AssertionError("guarded_client accepted the ops instance")
    t.tln(f"  calls made: {Recording.calls}")
    assert Recording.calls == [], "refused before connecting, so before any delete"

    t.h1("guarded_client() pointed at a booktest env")
    client = guarded_client(url="https://shared.aito.ai/db/x/env/booktest", key="k", client_class=Recording)
    t.tln(f"  calls made: {Recording.calls}")
    assert isinstance(client, Recording)
