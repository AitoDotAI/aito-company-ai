"""aito.ai's content map: what each page is about (plan C1, docs/44).

aito.ai publishes /content-map.json, version 1: {"version": 1, "pages":
{key: entry}}. A key is a page written as company-ai writes it (aito.ai's
own pages bare, "/pricing/"; other hosts host-first, "erp.aito.ai/rules/").
An entry has a kind, an item (or a demo's items) and, for use cases and
demos, a category, subcategory, verticals and domains.

The pull puts these on web_sessions and web_steps as whitespace Text, so
pooled counts are one Aito _relate. This is a lookup of published labels,
not a score (rule 2). A malformed map raises with its entry; a page the map
doesn't name is counted as unmapped, never guessed (rule 3).
"""

import requests

URL = "https://aito.ai/content-map.json"
VERSION = 1
KINDS = {"page", "post", "usecase", "demo", "solution"}
LISTS = ("items", "verticals", "domains")
SCALARS = ("item", "kind", "category", "subcategory")
# the stored columns, in the order the book and the reads show them
FIELDS = ("items", "categories", "subcategories", "verticals", "domains")


def _token(key: str, entry: dict, value) -> str:
    assert isinstance(value, str) and value and not any(c.isspace() for c in value), \
        f"content map {key!r}: {value!r} is not one whitespace-free token: {entry}"
    return value


def parse(data: dict) -> dict[str, dict]:
    """The map as {page: {kind, items, categories, subcategories, verticals,
    domains}}, every value a list of tokens. Raises on anything unexpected."""
    assert isinstance(data, dict) and data.get("version") == VERSION, \
        f"content map: version {data.get('version') if isinstance(data, dict) else data!r}, expected {VERSION}"
    assert set(data) == {"version", "pages"}, f"content map: unknown top-level keys {sorted(set(data))}"
    pages = data["pages"]
    assert isinstance(pages, dict) and pages, "content map: no pages"
    out = {}
    for key, entry in pages.items():
        assert isinstance(key, str) and key and not any(c in key for c in "?# ") and \
            not any(c.isspace() for c in key), f"content map: bad page key {key!r}: {entry}"
        assert isinstance(entry, dict), f"content map {key!r}: not an object: {entry!r}"
        unknown = set(entry) - set(LISTS) - set(SCALARS)
        assert not unknown, f"content map {key!r}: unknown fields {sorted(unknown)}: {entry}"
        assert entry.get("kind") in KINDS, \
            f"content map {key!r}: kind {entry.get('kind')!r}, expected one of {sorted(KINDS)}: {entry}"
        for name in LISTS:
            assert isinstance(entry.get(name, []), list), f"content map {key!r}: {name} is not a list: {entry}"
        assert ("item" in entry) != ("items" in entry), \
            f"content map {key!r}: needs exactly one of item and items: {entry}"
        items = [entry["item"]] if "item" in entry else entry["items"]
        assert items, f"content map {key!r}: no items: {entry}"
        out[key] = {
            "kind": _token(key, entry, entry["kind"]),
            "items": [_token(key, entry, v) for v in items],
            "categories": [_token(key, entry, entry["category"])] if "category" in entry else [],
            "subcategories": [_token(key, entry, entry["subcategory"])] if "subcategory" in entry else [],
            "verticals": [_token(key, entry, v) for v in entry.get("verticals", [])],
            "domains": [_token(key, entry, v) for v in entry.get("domains", [])],
        }
    return out


def fetch(url: str = URL) -> dict[str, dict]:
    """The published map, parsed. Any failure raises: a pull without it would
    write rows that look unlabelled for the wrong reason."""
    response = requests.get(url, timeout=30, headers={"User-Agent": "aito-company-ai web pull"})
    assert response.status_code == 200, f"content map {url}: HTTP {response.status_code}"
    return parse(response.json())


def labels(pages: list[str], cmap: dict[str, dict]) -> dict:
    """The columns for a visit (or one step) over `pages`, in order and once
    each, None where nothing applies; and `unmapped_pages`, how many of the
    pages (repeats counted) the map doesn't name."""
    out: dict[str, list[str]] = {f: [] for f in FIELDS}
    unmapped = 0
    for page in pages:
        entry = cmap.get(page)
        if entry is None:
            unmapped += 1
            continue
        for f in FIELDS:
            out[f] += [v for v in entry[f] if v not in out[f]]
    return {**{f: " ".join(v) or None for f, v in out.items()}, "unmapped_pages": unmapped}
