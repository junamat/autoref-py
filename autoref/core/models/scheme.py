from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrderScheme:
    """Declarative bracket-match order. Roles are roll ranks (0 = roll winner).

    For the common 2-team case, "first" means the role that acts before the other;
    subsequent actions round-robin by rank. ABAB rotates straight; ABBA rotates
    and reverses within each doubled step (2-team only — ignored for N>2).

    `split_ban_after_pick` triggers a second ban round after N picks; half the
    total bans run before picks, the remaining half after the threshold.
    """
    name: str
    protect_first: int = 0
    ban_first: int = 0
    pick_first: int = 0
    ban_pattern: str = "ABAB"
    split_ban_after_pick: int | None = None
