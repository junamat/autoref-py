"""Score predicates — decide which rows count toward a metric's population."""
from __future__ import annotations

from typing import Callable, Mapping


ScorePredicate = Callable[[Mapping], bool]


def include_all(row: Mapping) -> bool:
    """Default: keep every row."""
    return True


def exclude_failed(row: Mapping) -> bool:
    """Drop rows where the player failed (passed == 0/False)."""
    return bool(row.get("passed"))
