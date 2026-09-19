# is_local_instance / instance_host

  local=True  host=localhost
  local=True  host=127.0.0.1
  local=True  host=0.0.0.0
  local=False host=aito.example.com/db/aito
  local=False host=aito-demo.example.com/db/demo

## seed guard: --seed blocked unless local or --force

  seed url=localhost                    force=False -> allowed
  seed url=localhost                    force=True  -> allowed
  seed url=aito.example.com/db/aito     force=False -> BLOCKED
  seed url=aito.example.com/db/aito     force=True  -> allowed
