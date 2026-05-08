from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Timers:
    pick: int = 120
    ban: int = 120
    protect: int = 120
    ready_up: int = 90
    start_map: int = 5
    force_start: int = 10
    between_maps: int = 5
    closing: int = 30
