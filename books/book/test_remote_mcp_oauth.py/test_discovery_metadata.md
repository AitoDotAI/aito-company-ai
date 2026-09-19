# OAuth discovery — the two .well-known documents claude.ai fetches first


## protected-resource metadata (points /mcp at its authorization server)

status                 200
resource               http://localhost:8770/mcp
authorization_servers  ['http://localhost:8770/']

## authorization-server metadata (the endpoint map)

status                    200
issuer                    http://localhost:8770/
authorization_endpoint    http://localhost:8770/authorize
token_endpoint            http://localhost:8770/token
registration_endpoint     http://localhost:8770/register
revocation_endpoint       http://localhost:8770/revoke
grant_types_supported     ['authorization_code', 'refresh_token']
code_challenge_methods     ['S256']
token_endpoint_auth       ['client_secret_post', 'client_secret_basic', 'none']
revocation_endpoint_auth  ['client_secret_post', 'client_secret_basic']
