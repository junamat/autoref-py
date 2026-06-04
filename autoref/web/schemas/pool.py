from typing import Any, TypedDict


class PoolSummary(TypedDict):
    id: str
    name: str


class StatsDefaults(TypedDict, total=False):
    qualifier_method: str
    method: str
    count_failed: bool
    aggregate: str
    scope: str


class PoolDetail(TypedDict, total=False):
    id: str
    name: str
    tree: list[Any]
    stats_defaults: StatsDefaults
