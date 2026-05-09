from typing import TypedDict


class MatchSummary(TypedDict, total=False):
    id: str
    status: str
    active: bool
    orphaned: bool
    qualifier: bool
    mode: str
    team_names: list[str]
    best_of: int | None
    ref_name: str | None
    maps_played: int | None
    total_maps: int | None
    phase: str | None
    controller_type: str | None
    bancho_lobby_id: int | None
    orphaned_since: int | None
