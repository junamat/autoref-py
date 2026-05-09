from typing import Any, TypedDict


class PoolSummary(TypedDict):
    id: str
    name: str


class PoolDetail(TypedDict):
    id: str
    name: str
    tree: list[Any]
