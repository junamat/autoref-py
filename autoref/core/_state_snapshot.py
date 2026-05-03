"""Pure-fn builder for AutoRef state snapshots consumed by web/CLI hooks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .enums import MapState
from .utils import normalize_name as _normalize, find_map as _find_map

if TYPE_CHECKING:
    from .ref.base import AutoRef


def build_state(ref: "AutoRef") -> dict:
    """Build a serialisable state snapshot for the given AutoRef."""
    played_ids: set[int] = set()
    if not ref.match.match_status.empty:
        for bid in ref.match.match_status.loc[
            ref.match.match_status["step"] == "PICK", "beatmap_id"
        ]:
            played_ids.add(int(bid))

    maps = []
    for pm in ref.match.pool.flatten():
        if int(pm.beatmap_id) in played_ids:
            map_state = "played"
        elif pm.state == MapState.BANNED:
            map_state = "banned"
        elif pm.state == MapState.PROTECTED:
            map_state = "protected"
        elif pm.state == MapState.DISALLOWED:
            map_state = "disallowed"
        else:
            map_state = "pickable"
        maps.append({
            "code": pm.name or str(pm.beatmap_id),
            "state": map_state,
            "tb": getattr(pm, "is_tiebreaker", False),
        })

    events = []
    for _, row in ref.match.match_status.iterrows():
        ti = int(row["team_index"])
        team_name = (
            ref.match.teams[ti].name if ti < len(ref.match.teams) else str(ti)
        )
        pm = _find_map(ref.match, int(row["beatmap_id"]))
        map_code = pm.name if pm and pm.name else str(row["beatmap_id"])
        events.append({"step": str(row["step"]), "team": team_name, "map": map_code})

    # Build a username→ready lookup from the latest !mp settings fetch
    ready_map: dict[str, bool] = {
        _normalize(s.username): s.ready for s in ref.lobby.slot_info
    }
    present: set[str] = {_normalize(u) for u in ref.lobby.players}

    teams = [
        {"name": t.name, "players": [
            {
                "username": p.username,
                "present": _normalize(p.username) in present,
                "ready": ready_map.get(_normalize(p.username), False),
            }
            for p in t.players
        ]}
        for t in ref.match.teams
    ]

    return {
        "mode": ref.mode.value,
        "team_names": [t.name for t in ref.match.teams],
        "teams": teams,
        "best_of": ref.match.ruleset.best_of,
        "maps": maps,
        "events": events,
        "pending_proposal": ref._pending_proposal,
        "ref_name": getattr(ref._client, "username", None),
        "room_id": ref.lobby.room_id,
        "commands": [c.to_dict() for c in ref._commands()],
    }
