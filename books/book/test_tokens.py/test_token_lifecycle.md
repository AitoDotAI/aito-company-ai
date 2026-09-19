# mint a token — plaintext returned once, only the hash stored

returned a plaintext secret: True (len 54)
stored row has token_hash, not the secret: True
hash == sha256(secret): True

# verify: the secret works; wrong / empty / master

verify(secret):        True
verify('wrong'):       False
verify(''):            False
verify(master, master):True

# listing never exposes the hash

list fields: ['active', 'created', 'label', 'prefix', 'token_id']
hash absent from listing: True

# revoke — immediate, no caching

verify(secret) after revoke: False
listed active after revoke:  [False]

# a bad label is refused (rule 3)

  refused: a token needs a label
