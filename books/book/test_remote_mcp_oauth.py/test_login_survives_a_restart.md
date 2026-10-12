# 1. connect once, on the first process

/mcp with the access token          → 200

## the state file

mode                                → 0o600
clients / access / refresh          → 1 / 1 / 1
plaintext access token in the file  → False
plaintext refresh token in the file → False
keyed by the token's sha256         → True

# 2. restart: a new app on the same file

/mcp with the old access token      → 200
refresh with the old refresh token  → 200
/mcp with the rotated token         → 200
/mcp with the pre-rotation token    → 401

# 3. without a state file a restart logs the connector out (the old behaviour)

/mcp after an in-memory restart     → 401
