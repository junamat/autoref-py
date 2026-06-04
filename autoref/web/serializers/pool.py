from ..schemas.pool import PoolDetail, PoolSummary, StatsDefaults


def pool_to_summary(pool: dict) -> PoolSummary:
    """Extract id+name from a pool store dict."""
    return PoolSummary(id=pool["id"], name=pool.get("name", ""))


def pool_to_detail(pool: dict) -> PoolDetail:
    """Full pool dict including tree and stats_defaults."""
    result: PoolDetail = {
        "id": pool["id"],
        "name": pool.get("name", ""),
        "tree": pool.get("tree", []),
    }
    if "stats_defaults" in pool:
        result["stats_defaults"] = pool["stats_defaults"]
    return result
