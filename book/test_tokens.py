"""API tokens for the remote MCP (docs/28).

The security contract: the plaintext is generated server-side, returned once,
and only its hash is stored; verify() accepts the env master or any active
stored token and rejects everything else; revoking is immediate; and listing
never exposes the hash. Requires a running Aito.

Prints stay secret/id/date-free (the token, its id, prefix, and created date are
random/stamped) — only booleans and labels, so the snapshot is stable.
"""

import booktest as bt

from company_ai import log, schema, tokens
from company_ai.aito import AitoClient
from company_ai.config import Config


def _client() -> AitoClient:
    config = Config.from_env()
    c = AitoClient(config.instance_url, config.api_key)
    c.delete_table("tokens")
    c.create_table("tokens", schema.TOKENS)
    return c


def test_token_lifecycle(t: bt.TestCaseRun) -> None:
    client = _client()

    t.h1("mint a token — plaintext returned once, only the hash stored")
    made = log.add_token(client, "the operator's claude.ai connector")
    secret = made["token"]
    stored = client.query({"from": "tokens", "limit": 10})["hits"][0]
    t.tln(f"returned a plaintext secret: {bool(secret)} (len {len(secret)})")
    t.tln(f"stored row has token_hash, not the secret: "
          f"{'token_hash' in stored and secret not in stored.values()}")
    t.tln(f"hash == sha256(secret): {stored['token_hash'] == tokens.hash_token(secret)}")

    t.h1("verify: the secret works; wrong / empty / master")
    t.tln(f"verify(secret):        {tokens.verify(client, secret)}")
    t.tln(f"verify('wrong'):       {tokens.verify(client, 'wrong')}")
    t.tln(f"verify(''):            {tokens.verify(client, '')}")
    t.tln(f"verify(master, master):{tokens.verify(client, 'MASTER', master='MASTER')}")

    t.h1("listing never exposes the hash")
    listed = tokens.list_tokens(client)
    t.tln(f"list fields: {sorted(listed[0].keys())}")
    t.tln(f"hash absent from listing: {'token_hash' not in listed[0]}")

    t.h1("revoke — immediate, no caching")
    log.revoke_token(client, made["token_id"])
    t.tln(f"verify(secret) after revoke: {tokens.verify(client, secret)}")
    t.tln(f"listed active after revoke:  {[x['active'] for x in tokens.list_tokens(client)]}")

    t.h1("a bad label is refused (rule 3)")
    try:
        log.add_token(client, "  ")
    except AssertionError as e:
        t.tln(f"  refused: {e}")
