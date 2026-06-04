"""Parse osu! multiplayer match URLs to extract match IDs."""
from __future__ import annotations

import re
from typing import NamedTuple


class MpLink(NamedTuple):
    match_id: int
    game_id: int | None


_MP_PATTERNS = [
    re.compile(r"osu\.ppy\.sh/mp/(\d+)(?:/(\d+))?"),
    re.compile(r"osu\.ppy\.sh/community/matches/(\d+)(?:/(\d+))?"),
]


def parse_mp_link(url: str) -> MpLink | None:
    """Extract match_id (and optional game_id) from an osu! mp URL.

    Supports:
        https://osu.ppy.sh/mp/123456
        https://osu.ppy.sh/mp/123456/789
        https://osu.ppy.sh/community/matches/123456
        https://osu.ppy.sh/community/matches/123456/789

    Returns None if the URL doesn't match any known pattern.
    """
    for pattern in _MP_PATTERNS:
        m = pattern.search(url)
        if m:
            match_id = int(m.group(1))
            game_id = int(m.group(2)) if m.group(2) else None
            return MpLink(match_id, game_id)
    return None
