"""Server-side storage for the assistant's conversations — in Aito, so history
is durable across cache-clears, restarts, and devices without any container
filesystem. One row per message in `chat_messages` (schema.py); a conversation
is replaced on save via a filtered _delete + a batch insert (no full-table
rewrite). This is operator data — the pipeline discussed in chat — living in the
same instance as the rest (docs/06). The frontend store syncs to these
endpoints; localStorage stays the offline cache.
"""

import json
import re

from . import schema
from .aito import AitoClient

# a safe conversation id: no separators/dots/traversal
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _check_id(cid: str) -> None:
    assert cid and _ID.match(cid), f"bad conversation id {cid!r}"


def _ensure(client: AitoClient) -> None:
    client.ensure_table("chat_messages", schema.CHAT_MESSAGES)


def _msg(row: dict) -> dict:
    msg = {"role": row["role"], "content": row.get("content") or ""}
    if row.get("trace"):
        try:
            msg["trace"] = json.loads(row["trace"])
        except (ValueError, TypeError):
            pass
    return msg


def _conversation(rows: list[dict]) -> dict:
    """Assemble one conversation from its message rows (ordered by seq)."""
    rows = sorted(rows, key=lambda r: r.get("seq", 0))
    last = rows[-1]
    return {"id": last["conversation_id"], "title": last.get("title") or "New chat",
            "updated": int(last.get("updated") or 0), "msgs": [_msg(r) for r in rows]}


def list_chats(client: AitoClient) -> list[dict]:
    """Every stored conversation, newest first."""
    _ensure(client)
    rows = client.query({"from": "chat_messages", "limit": 100000})["hits"]
    by_conv: dict[str, list] = {}
    for r in rows:
        by_conv.setdefault(r["conversation_id"], []).append(r)
    out = [_conversation(rs) for rs in by_conv.values()]
    out.sort(key=lambda c: c["updated"], reverse=True)
    return out


def get_chat(client: AitoClient, cid: str) -> dict | None:
    _check_id(cid)
    _ensure(client)
    rows = client.query({"from": "chat_messages",
                         "where": {"conversation_id": cid}, "limit": 100000})["hits"]
    return _conversation(rows) if rows else None


def _replace_conversation(client: AitoClient, cid: str, add_rows: list[dict]) -> int:
    """Replace one conversation's messages: delete its rows by predicate,
    insert the new ones, and read back that exactly those landed (rule 3).
    Other conversations are never touched, so two saves at once cannot erase
    each other (td-20261012114045038839). The predicate delete is safe since
    docs/24 bug 4 stopped reproducing (book/test_modify_visibility.py re-probes
    it). Returns the number of rows dropped."""
    where = {"conversation_id": cid}
    dropped = client.query({"from": "chat_messages", "where": where, "limit": 0})["total"]
    if dropped:
        client.delete_entries("chat_messages", where)
    if add_rows:
        client.upload_batch("chat_messages", add_rows)
    got = sorted(r["message_id"] for r in client.query(
        {"from": "chat_messages", "where": where, "select": ["message_id"],
         "limit": 100000})["hits"])
    assert got == sorted(r["message_id"] for r in add_rows), \
        f"chat {cid}: wrote {len(add_rows)} messages, read back {got}"
    return dropped


def save_chat(client: AitoClient, cid: str, title: str | None,
              msgs: list | None, updated: int | None) -> dict:
    """Create or replace a conversation. The id is validated (no traversal).
    Empty conversations aren't stored (a fresh thread persists once you type)."""
    _check_id(cid)
    _ensure(client)
    rows = []
    for i, m in enumerate(msgs or []):
        rows.append({
            "message_id": f"{cid}-{i}", "conversation_id": cid, "seq": i,
            "role": m.get("role") or "user", "content": m.get("content") or "",
            "trace": json.dumps(m["trace"]) if m.get("trace") is not None else None,
            "title": title or "New chat", "updated": str(int(updated or 0)), "created": "",
        })
    _replace_conversation(client, cid, rows)
    return {"id": cid, "title": title or "New chat", "updated": updated or 0, "count": len(rows)}


def remove_chat(client: AitoClient, cid: str) -> dict:
    _check_id(cid)
    _ensure(client)
    dropped = _replace_conversation(client, cid, [])
    return {"removed": cid, "deleted": dropped}
