"""Result type: Ok[T] | Err.

Thin wrapper to carry error context instead of returning None.
Usage::

    result = await compute_pp(...)
    if not result:        # Err
        log(result.reason)
    else:
        use(result.value) # Ok
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class Ok(Generic[T]):
    value: T

    def __bool__(self) -> bool:
        return True


@dataclass(slots=True)
class Err:
    reason: str
    exc: BaseException | None = field(default=None, compare=False, repr=False)

    def __bool__(self) -> bool:
        return False
