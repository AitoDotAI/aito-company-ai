# the bearer gate

no Authorization header      → 401
wrong token                  → 401
correct token (initialize)   → 200
bare /mcp works, no redirect → True
dashboard /api/docs still up  → 200
