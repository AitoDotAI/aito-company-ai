"""Process-wide booktest setup (booktest auto-detects this module + the
`process_setup_teardown` generator).

The suite RESEEDS — `create_schema` drops and recreates tables — so it must
never run against anything but a disposable test env. Ambient `AITO_INSTANCE_URL`
or a stray `COMPANY_AI_ENV=.env.aito` would otherwise point the reseeding suite
at production (that is how production got reseeded once already). This setup:

  1. forces the config source to `.env.test` (overriding any ambient env), and
  2. asserts the resolved instance is a *dedicated test env* — refusing to run
     otherwise, loudly (rule 3).

To run the suite you provide `.env.test` pointing at a booktest env (see
CONTRIBUTING.md). There is deliberately no override flag: the guard is the point.
"""
import os

from company_ai.config import REPO_ROOT, Config, instance_host


def process_setup_teardown():
    env_test = REPO_ROOT / ".env.test"
    assert env_test.exists(), (
        ".env.test is required to run the booktest suite. Copy .env.example to "
        ".env.test and point AITO_INSTANCE_URL at a DEDICATED test env (a throwaway "
        "Aito env — the suite drops and recreates tables). See CONTRIBUTING.md."
    )

    # Force .env.test as the one config source: override any ambient COMPANY_AI_ENV,
    # clear a leaked AITO_INSTANCE_URL so .env.test's value resolves, and clear the
    # ambient private COMPANY_AI_DATA_DIR (the shellHook sets it from .env) so the
    # test process has no path to the private dataset at all.
    os.environ["COMPANY_AI_ENV"] = str(env_test)
    os.environ.pop("AITO_INSTANCE_URL", None)
    os.environ.pop("COMPANY_AI_DATA_DIR", None)

    cfg = Config.from_env()
    url, host = cfg.instance_url, instance_host(cfg.instance_url)

    # The target must be an explicitly-marked test env. "booktest"/"test" in the
    # path is the marker; production and any unmarked instance are refused.
    is_test_env = "/env/booktest" in url or "/env/test" in url or "test" in host
    assert is_test_env, (
        f"REFUSING to run the reseeding booktest suite against {host!r} ({url}). "
        "The suite drops tables; .env.test must point at a dedicated test env whose "
        "path contains 'booktest' or 'test'. This guard has no override — fix "
        ".env.test instead."
    )

    # A test env must never carry the private dataset (docs/06-privacy).
    assert cfg.data_dir is None or "seed" in str(cfg.data_dir), (
        f"a test env must not load the private dataset ({cfg.data_dir}); "
        "leave COMPANY_AI_DATA_DIR unset in .env.test."
    )

    yield  # ---- the whole suite runs here, pinned to the verified test env ----
    # Nothing to tear down: the test env is disposable and each test reseeds it.
