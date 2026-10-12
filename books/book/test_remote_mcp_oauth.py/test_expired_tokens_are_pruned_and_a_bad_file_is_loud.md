# expiry is applied when the file is read back

issued                         → clients 1, access 1, refresh 1, pairs 2
after 2 h: access token loads  → False
after 2 h: refresh token loads → True
after 2 h: file                → clients 1, access 0, refresh 1, pairs 0
after 31 d: refresh token loads → False
after 31 d: file               → clients 1, access 0, refresh 0, pairs 0  (the client stays registered)

# an expired access token does not take its refresh token with it

expired access token loads     → False
its refresh token still loads  → True

# a file that cannot be read stops the start, naming the path

cannot read the OAuth state file <path> (COMPANY_AI_OAUTH_STATE): JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
