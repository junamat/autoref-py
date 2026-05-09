import json
from typing import TYPE_CHECKING, Any

from ..schemas.match import MatchSummary

if TYPE_CHECKING:
    from ..server import WebInterface


def active_to_summary(iface: "WebInterface") -> MatchSummary:
    """Serialize a live WebInterface to MatchSummary."""
    s: dict[str, Any] = iface._last_state or {}
    return MatchSummary(
        id=iface.match_id,
        active=True,
        qualifier=s.get("qualifier", False),
        mode=s.get("mode", "off"),
        team_names=s.get("team_names", []),
        best_of=s.get("best_of"),
        ref_name=s.get("ref_name"),
        maps_played=s.get("maps_played"),
        total_maps=s.get("total_maps"),
        phase=s.get("phase"),
    )


def pending_to_summary(match_id: str, payload: dict) -> MatchSummary:
    """Serialize a pending (not yet started) match payload to MatchSummary."""
    teams = payload.get("teams", [])
    return MatchSummary(
        id=match_id,
        status="pending",
        qualifier=payload.get("type") == "qualifiers",
        mode=payload.get("mode", "off"),
        team_names=[t["name"] for t in teams],
        best_of=payload.get("best_of"),
    )


def orphan_to_summary(row: dict) -> MatchSummary:
    """Serialize a live_matches DB row for an orphaned match to MatchSummary."""
    payload = json.loads(row.get("payload_json") or "{}")
    teams = payload.get("teams", [])
    return MatchSummary(
        id=row["match_id"],
        status=row.get("status", "orphaned"),
        orphaned=True,
        qualifier=payload.get("type") == "qualifiers",
        controller_type=row.get("controller_type"),
        team_names=[t["name"] for t in teams],
        best_of=payload.get("best_of"),
        bancho_lobby_id=row.get("bancho_lobby_id"),
        orphaned_since=row.get("updated_at"),
    )
