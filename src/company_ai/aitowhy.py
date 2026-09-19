"""Parsing helpers for Aito's `$why` explanation tree.

v2 nests the per-driver `relatedPropositionLift` factors under an inner
`product` factor (v1 had them at the top level), so they must be walked
recursively. Proposition values are also direct in v2 (`{"channel": "call"}`)
rather than wrapped (`{"channel": {"$has": "call"}}`) — `prop_value` handles both.
"""


def lift_factors(hit: dict) -> list[dict]:
    """Every `relatedPropositionLift` factor in the hit's `$why` tree, at any
    depth. Each factor keeps its Aito shape: {type, proposition, value}."""
    out: list[dict] = []

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "relatedPropositionLift":
            out.append(node)
        for sub in node.get("factors", []):
            walk(sub)

    walk(hit.get("$why", {}))
    return out


def prop_value(prop: dict):
    """The value of a single-field `$why` proposition — direct in v2, or the
    `{"$has": value}` wrapper on older responses."""
    inner = next(iter(prop.values()))
    return inner.get("$has") if isinstance(inner, dict) else inner
