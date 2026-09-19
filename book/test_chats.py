"""Conversation storage in Aito (schema.chat_messages, one row per message).
Durable across devices/restarts, no container filesystem. No LLM — just the
store and its id safety."""

import booktest as bt

from company_ai import chats, loaders, schema
from company_ai.aito import AitoClient
from company_ai.config import Config


def _client() -> AitoClient:
    config = Config.from_env()
    return AitoClient(config.instance_url, config.api_key)


def test_chats_store_roundtrip(t: bt.TestCaseRun) -> None:
    client = _client()
    loaders.create_schema(client)
    # isolate from other runs: start from an empty chat_messages table
    client.delete_table("chat_messages")
    client.create_table("chat_messages", schema.CHAT_MESSAGES)

    t.h1("save two conversations, list them newest-first")
    chats.save_chat(client, "c-abc", "How's my pipeline?",
                    [{"role": "user", "content": "hi"}], 100)
    chats.save_chat(client, "c-def", "Marketing ideas",
                    [{"role": "user", "content": "ideas?"},
                     {"role": "assistant", "content": "post more",
                      "trace": [{"tool": "score_post", "ok": True}]}], 200)
    listed = chats.list_chats(client)
    t.tln(f"list: {[(c['id'], c['title'], c['updated']) for c in listed]}")

    t.h1("get one back, with its messages and a round-tripped tool trace")
    got = chats.get_chat(client, "c-def")
    t.tln(f"c-def msgs: {got['msgs']}")

    t.h1("overwrite (replace the conversation), then remove")
    chats.save_chat(client, "c-abc", "How's my pipeline (edited)",
                    [{"role": "user", "content": "hi"},
                     {"role": "assistant", "content": "15 open deals"}], 300)
    t.tln(f"after edit, newest-first ids: {[c['id'] for c in chats.list_chats(client)]}")
    t.tln(f"remove c-abc: {chats.remove_chat(client, 'c-abc')}")
    t.tln(f"remaining: {[c['id'] for c in chats.list_chats(client)]}")
    t.tln(f"remove missing: {chats.remove_chat(client, 'c-nope')}")

    t.h1("a bad id is refused — no path traversal, no odd names")
    for bad in ("../evil", "a/b", "with.dot", ""):
        try:
            chats.save_chat(client, bad, "x", [{"role": "user", "content": "y"}], 1)
            raise RuntimeError(f"accepted bad id {bad!r}")
        except AssertionError as e:
            t.tln(f"  {bad!r} -> {e}")
