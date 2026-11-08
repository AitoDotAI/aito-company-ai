# is_test_instance

  https://shared.aito.ai/db/x/env/booktest: True
  https://shared.aito.ai/db/x/env/test: True
  https://test.aito.app: True
  https://test-company-ai.aito.app: True
  https://internal.aito.ai/db/aito: False
  https://aito-company-ai.aito.app: False
  http://localhost:9005: False
  https://latest.aito.ai/db/aito: False
  https://contest-db.aito.app: False
  https://aito-test.aito.app: False
  https://shared.aito.ai/db/x/env/test-prod: False
  https://shared.aito.ai/db/x/env/testdrive: False
  https://internal.aito.ai/db/aito?x=/env/test: False
  https://internal.aito.ai/db/aito#/env/booktest: False

# guarded_client() pointed at the ops instance

  refused: REFUSING: internal.aito.ai/db/aito (https://internal.aito.ai/db/aito) is not a dedicated test env, and this book deletes and reseeds tables. Point .env.test at a booktest env.
  calls made: []

# guarded_client() pointed at a booktest env

  calls made: [('connect', 'https://shared.aito.ai/db/x/env/booktest')]
