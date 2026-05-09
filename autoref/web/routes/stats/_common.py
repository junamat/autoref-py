from ..._state import _POOL_STORE, _build_map_code_lookup, _build_map_order_lookup

__all__ = ["_POOL_STORE", "_build_map_code_lookup", "_build_map_order_lookup", "predicate_for"]


def predicate_for(count_failed: bool):
    from ....core.stats import exclude_failed, include_all
    return include_all if count_failed else exclude_failed
