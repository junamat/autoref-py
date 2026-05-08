from __future__ import annotations


def match_filter(pool_id: str | None, round_name: str | None,
                 alias: str = "") -> tuple[str, list]:
    """Build an optional match_id IN (...) clause for pool/round filtering.

    Returns ('', []) when neither filter is active.
    `alias` qualifies match_id for queries that join multiple tables.
    """
    conds: list[str] = []
    params: list[str] = []
    if pool_id:
        conds.append("pool_id = ?")
        params.append(pool_id)
    if round_name:
        conds.append("round_name = ?")
        params.append(round_name)
    if not conds:
        return "", []
    col = f"{alias}.match_id" if alias else "match_id"
    return f" {col} IN (SELECT match_id FROM matches WHERE {' AND '.join(conds)}) ", params
