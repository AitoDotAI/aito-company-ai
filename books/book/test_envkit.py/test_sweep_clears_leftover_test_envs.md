SKIPPED — env-management test. It creates/drops envs at the db level,
which is destructive on a shared multi-env instance. To run it, set
COMPANY_AI_ENV_TESTS=1 against a disposable single-tenant instance
(e.g. a local Aito container), never the shared demo.
