# is_test_instance

  https://internal.aito.ai/db/aito: False
  https://aito-company-ai.aito.app: False
  http://localhost:9005: False
  https://shared.aito.ai/db/x/env/booktest: True
  https://aito-test.aito.app: True

# guarded_client() pointed at the ops instance

  refused: REFUSING: internal.aito.ai/db/aito (https://internal.aito.ai/db/aito) is not a dedicated test env, and this book deletes and reseeds tables. Point .env.test at a booktest env.
  calls made: []

# guarded_client() pointed at a booktest env

  calls made: [('connect', 'https://shared.aito.ai/db/x/env/booktest')]
