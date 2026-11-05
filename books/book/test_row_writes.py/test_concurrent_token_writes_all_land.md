# Tokens before

3 rows, all active

# Two revokes and one new token at once

revoke 0: ok
revoke 1: ok
add_token: ok

# Tokens after

4 rows
token 0 active=False
token 1 active=False
token 2 active=True
