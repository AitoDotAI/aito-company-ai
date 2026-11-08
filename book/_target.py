"""The client a book that deletes or reseeds takes: refused unless its
instance is a dedicated test env (config.is_test_instance), before any call.

book/__booktest__.py already pins the whole suite to .env.test and checks
the same rule; this applies it again where the client is made, so a book
function run outside the suite (a script, a REPL with COMPANY_AI_ENV set to
the ops instance) can't drop tables there either (CPO review of #93)."""

from company_ai.aito import AitoClient
from company_ai.config import Config, instance_host, is_test_instance


def guarded_client(url: str | None = None, key: str | None = None, client_class=AitoClient):
    """An Aito client for a test env, or AssertionError naming the instance."""
    if url is None:
        config = Config.from_env()
        url, key = config.instance_url, config.api_key
    if not is_test_instance(url):
        raise AssertionError(
            f"REFUSING: {instance_host(url)} ({url}) is not a dedicated test env, and this "
            "book deletes and reseeds tables. Point .env.test at a booktest env.")
    return client_class(url, key)
