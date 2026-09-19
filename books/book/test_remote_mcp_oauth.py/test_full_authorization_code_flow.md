# 1. dynamic client registration (claude.ai self-registers)

POST /register            → 201
client_id issued          → True
redirect_uris echoed      → ['https://claude.ai/api/mcp/auth_callback']

# 2. authorize with PKCE → 302 back to the client with a code

GET /authorize            → 302
redirect host+path        → https://claude.ai/api/mcp/auth_callback
state preserved           → True
code returned             → True

# 3. exchange the code (+ PKCE verifier) for tokens

POST /token               → 200
token_type                → Bearer
expires_in                → 3600
access + refresh issued   → True

# 4. wrong PKCE verifier is rejected (the code is single-use)

POST /token wrong verifier → 400 (invalid_grant)

# 5. call /mcp — OAuth token AND named/master token pass one gate

OAuth access token        → 200
named/master bearer token → 200
no token                  → 401
wrong token               → 401

# 6. refresh rotates the token pair

POST /token (refresh)     → 200
new access token issued   → True
