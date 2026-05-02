"""Shared web-layer state and helpers used across route modules."""
from pathlib import Path

from ..core.pool_store import PoolStore

_STATIC_DIR = Path(__file__).parent / "static"

_POOL_STORE = PoolStore()


def _flatten_pool_tree(nodes: list, parent_mods: str = "") -> list:
    from ..factory import flatten_pool_tree as _ft
    return _ft(nodes, parent_mods)


def _build_map_code_lookup() -> dict[int, str]:
    """Walk every saved pool, return {beatmap_id: code} (e.g. {3814680: "NM1"}).

    On collisions across pools, the last one wins. Acceptable for one-tournament
    use; revisit if multi-tournament aggregation becomes a real use case.
    """
    lookup: dict[int, str] = {}

    def _walk(nodes):
        for n in nodes:
            if n.get("type") == "map":
                bid = n.get("bid")
                code = n.get("code")
                if bid and code:
                    try:
                        lookup[int(bid)] = str(code)
                    except (TypeError, ValueError):
                        pass
            elif n.get("children"):
                _walk(n["children"])

    for pool in _POOL_STORE.list():
        _walk(pool.get("tree", []))
    return lookup


def _build_map_order_lookup() -> dict[int, int]:
    """Walk every saved pool in tree order, return {beatmap_id: position}.

    Position is the 0-based index of the map in the flattened pool tree
    (NM1=0, NM2=1, ..., HD1=N, ...). Used to sort standings/results maps
    in pool order rather than by pick count.
    """
    order: dict[int, int] = {}
    counter = 0

    def _walk(nodes):
        nonlocal counter
        for n in nodes:
            if n.get("type") == "map":
                bid = n.get("bid")
                if bid:
                    try:
                        bid_int = int(bid)
                        if bid_int not in order:
                            order[bid_int] = counter
                            counter += 1
                    except (TypeError, ValueError):
                        pass
            elif n.get("children"):
                _walk(n["children"])

    for pool in _POOL_STORE.list():
        _walk(pool.get("tree", []))
    return order
