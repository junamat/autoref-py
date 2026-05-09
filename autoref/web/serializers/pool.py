from ..schemas.pool import PoolDetail, PoolSummary


def pool_to_summary(pool: dict) -> PoolSummary:
    """Extract id+name from a pool store dict."""
    return PoolSummary(id=pool["id"], name=pool.get("name", ""))


def pool_to_detail(pool: dict) -> PoolDetail:
    """Full pool dict including tree."""
    return PoolDetail(
        id=pool["id"],
        name=pool.get("name", ""),
        tree=pool.get("tree", []),
    )
