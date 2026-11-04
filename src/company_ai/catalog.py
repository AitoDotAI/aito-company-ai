"""The marketing catalog read surface: materials, channels, posts.

Writes have always been there (log.add_material / add_channel / add_post /
log_post_result); these are the reads, so an agent can see what exists before
it adds, and a backfill catches a post or material already logged. Filters are
exact-value `where`s, validated against the schema's vocabularies (rule 3);
`title` finds materials by words of their title with Aito text match. No
prediction here — plumbing (rule 2).
"""

from . import schema
from .aito import AitoClient

LIMIT = 100000


def _where(**filters) -> dict:
    return {k: v for k, v in filters.items() if v is not None}


def _check(value, allowed: set, name: str) -> None:
    assert value is None or value in allowed, f"unknown {name} {value!r}; allowed {sorted(allowed)}"


def list_materials(client: AitoClient, title: str | None = None, type: str | None = None,
                   topic: str | None = None, lane: str | None = None) -> list[dict]:
    """Materials, newest first. `title` matches words of the title."""
    _check(type, schema.MATERIAL_TYPES, "type")
    _check(topic, schema.POST_TOPICS, "topic")
    _check(lane, schema.LANES, "lane")
    where = _where(type=type, topic=topic, lane=lane)
    if title:
        where["title"] = {"$match": title}
    return client.query({"from": "materials", "where": where,
                         "orderBy": {"$desc": "created"}, "limit": LIMIT})["hits"]


def list_channels(client: AitoClient, platform: str | None = None,
                  name: str | None = None) -> list[dict]:
    """Channels, by platform then name."""
    _check(platform, schema.PLATFORMS, "platform")
    rows = client.query({"from": "channels", "where": _where(platform=platform, name=name),
                         "limit": LIMIT})["hits"]
    return sorted(rows, key=lambda c: (c["platform"], c["name"]))


def list_posts(client: AitoClient, material_id: str | None = None,
               channel_id: str | None = None, status: str | None = None,
               platform: str | None = None) -> list[dict]:
    """Posts, newest posted first, then the unposted ones."""
    _check(status, schema.POST_STATUS, "status")
    _check(platform, schema.PLATFORMS, "platform")
    rows = client.query({"from": "posts", "where": _where(
        material_id=material_id, channel_id=channel_id, status=status, platform=platform),
        "limit": LIMIT})["hits"]
    posted = sorted((p for p in rows if p.get("posted_at")),
                    key=lambda p: (p.get("posted_at"), p["post_id"]), reverse=True)
    unposted = sorted((p for p in rows if not p.get("posted_at")), key=lambda p: p["post_id"])
    return posted + unposted
