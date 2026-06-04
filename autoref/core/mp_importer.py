"""Import osu! multiplayer matches from mp links into the database."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .mp_link import MpLink, parse_mp_link

if TYPE_CHECKING:
    from .db import MatchDatabase

logger = logging.getLogger(__name__)


@dataclass
class ImportedGame:
    beatmap_id: int
    scores: list[dict]
    start_time: str | None = None
    end_time: str | None = None


@dataclass
class ImportedMatch:
    match_id: int
    name: str
    games: list[ImportedGame] = field(default_factory=list)
    users: dict[int, str] = field(default_factory=dict)
    match_type: str = "TeamVs"
    start_time: str | None = None
    end_time: str | None = None


def _score_to_dict(s: Any, users: dict[int, str]) -> dict:
    mods: list[str] = []
    if s.mods:
        for m in s.mods:
            mods.append(m.acronym if hasattr(m, "acronym") else str(m))
    team = None
    match_obj = getattr(s, "match", None)
    if match_obj is not None:
        team = getattr(match_obj, "team", None)

    # Extract hit counts from statistics
    stats = getattr(s, "statistics", None)
    nmiss = getattr(stats, "count_miss", 0) if stats else 0
    n50 = getattr(stats, "count_50", 0) if stats else 0
    n100 = getattr(stats, "count_100", 0) if stats else 0
    n300 = getattr(stats, "count_300", 0) if stats else 0
    ngeki = getattr(stats, "count_geki", 0) if stats else 0
    nkatu = getattr(stats, "count_katu", 0) if stats else 0

    return {
        "user_id": int(s.user_id),
        "username": users.get(int(s.user_id)),
        "score": int(s.score),
        "accuracy": float(s.accuracy),
        "max_combo": int(s.max_combo),
        "passed": bool(s.passed),
        "perfect": bool(getattr(s, "perfect", False)),
        "mods": mods,
        "rank": s.rank.value if hasattr(s.rank, "value") else (s.rank or None),
        "team": team,
        "nmiss": int(nmiss),
        "n50": int(n50),
        "n100": int(n100),
        "n300": int(n300),
        "ngeki": int(ngeki),
        "nkatu": int(nkatu),
    }


async def fetch_mp_match(client: Any, mp_link: MpLink) -> ImportedMatch:
    """Fetch a multiplayer match from the osu! API.

    Args:
        client: aiosu.v2.Client instance
        mp_link: Parsed mp link with match_id

    Returns:
        ImportedMatch with all games and scores
    """
    resp = await client.get_multiplayer_match(mp_link.match_id)

    users: dict[int, str] = {}
    for u in getattr(resp, "users", None) or []:
        uid = getattr(u, "id", None)
        uname = getattr(u, "username", None)
        if uid is not None and uname is not None:
            users[int(uid)] = str(uname)

    match_info = getattr(resp, "match", resp)

    # Determine match type from first game's team_type, or default to HeadToHead
    match_type = "HeadToHead"
    for ev in resp.events:
        game = getattr(ev, "game", None)
        if game is not None:
            team_type = getattr(game, "team_type", None)
            if team_type:
                match_type = str(team_type).replace("-", "").replace("_", "")
                break

    games: list[ImportedGame] = []
    for ev in resp.events:
        game = getattr(ev, "game", None)
        if game is None:
            continue
        if game.end_time is None or not game.scores:
            continue

        scores = [_score_to_dict(s, users) for s in game.scores]
        games.append(ImportedGame(
            beatmap_id=game.beatmap_id,
            scores=scores,
            start_time=str(getattr(game, "start_time", "")),
            end_time=str(getattr(game, "end_time", "")),
        ))

    return ImportedMatch(
        match_id=mp_link.match_id,
        name=getattr(match_info, "name", f"MP {mp_link.match_id}"),
        games=games,
        users=users,
        match_type=match_type,
        start_time=str(getattr(match_info, "start_time", "")),
        end_time=str(getattr(match_info, "end_time", "")),
    )


def save_imported_match(
    db: "MatchDatabase",
    imported: ImportedMatch,
    *,
    pool_id: str | None = None,
    round_name: str | None = None,
) -> int:
    """Save an imported match to the database.

    Each player becomes their own team (like 1v1/qualifiers format).

    Args:
        db: MatchDatabase instance
        imported: ImportedMatch from fetch_mp_match
        pool_id: Optional pool identifier for stats filtering
        round_name: Optional round name for stats filtering

    Returns:
        The auto-assigned match_id in the database
    """
    # Sort players by user_id to get consistent team assignment
    sorted_users = sorted(imported.users.items())
    user_to_team: dict[int, int] = {uid: i for i, (uid, _) in enumerate(sorted_users)}

    cursor = db._conn.execute(
        "INSERT INTO matches "
        "(ruleset_vs, gamemode, win_condition, best_of, bans_per_team, "
        " protects_per_team, winner_team, pool_id, round_name, tb_beatmap_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,  # Always 1v1 format
            "STANDARD",
            "SCORE_V2",
            len(imported.games),
            "[]",
            "[]",
            None,
            pool_id,
            round_name,
            None,
        ),
    )
    assert cursor.lastrowid is not None
    mid = cursor.lastrowid

    # Each player is their own team
    for i, (_uid, uname) in enumerate(sorted_users):
        db.teams.insert_team(mid, i, uname)

    game_scores: list[tuple[int, int, list[dict]]] = []
    for turn, game in enumerate(imported.games, start=1):
        scores_for_game: list[dict] = []
        for s in game.scores:
            team_index = user_to_team.get(s["user_id"], 0)

            scores_for_game.append({
                "user_id": s["user_id"],
                "username": s.get("username"),
                "team_index": team_index,
                "score": s["score"],
                "accuracy": s["accuracy"],
                "max_combo": s["max_combo"],
                "mods": s["mods"],
                "passed": s["passed"],
                "perfect": s.get("perfect", False),
                "rank": s.get("rank"),
                "nmiss": s.get("nmiss", 0),
                "n50": s.get("n50", 0),
                "n100": s.get("n100", 0),
                "n300": s.get("n300", 0),
                "ngeki": s.get("ngeki", 0),
                "nkatu": s.get("nkatu", 0),
            })
        game_scores.append((turn, game.beatmap_id, scores_for_game))

    db.scores.insert_scores(mid, game_scores, {})
    db._conn.commit()
    return mid


async def save_imported_match_with_pp(
    db: "MatchDatabase",
    imported: ImportedMatch,
    *,
    pool_id: str | None = None,
    round_name: str | None = None,
) -> int:
    """Save an imported match and calculate PP values for all scores.

    This is an async version that calculates PP after saving, ensuring
    that PP-based stats and plots work immediately after import.

    Args:
        db: MatchDatabase instance
        imported: ImportedMatch from fetch_mp_match
        pool_id: Optional pool identifier for stats filtering
        round_name: Optional round name for stats filtering

    Returns:
        The auto-assigned match_id in the database
    """
    from .stats.leaderboards.pp import augment_pp

    # Save the match first
    mid = save_imported_match(db, imported, pool_id=pool_id, round_name=round_name)

    # Get all scores for this match and calculate PP
    scores = db.scores.by_match(mid)
    if not scores.empty:
        await augment_pp(scores, db=db)

    return mid


async def import_mp_link(
    db: "MatchDatabase",
    url: str,
    *,
    pool_id: str | None = None,
    round_name: str | None = None,
) -> int | None:
    """Import a match from an osu! mp link URL.

    Args:
        db: MatchDatabase instance
        url: osu! mp link (e.g. https://osu.ppy.sh/mp/123456)
        pool_id: Optional pool identifier
        round_name: Optional round name

    Returns:
        Database match_id on success, None on failure
    """
    from ..client import make_client

    mp_link = parse_mp_link(url)
    if mp_link is None:
        logger.error("Invalid mp link: %s", url)
        return None

    async with make_client() as client:
        imported = await fetch_mp_match(client, mp_link)

    if not imported.games:
        logger.warning("No games found in match %d", mp_link.match_id)
        return None

    return await save_imported_match_with_pp(db, imported, pool_id=pool_id, round_name=round_name)


async def import_mp_links(
    db: "MatchDatabase",
    urls: list[str],
    *,
    pool_id: str | None = None,
    round_name: str | None = None,
) -> list[int]:
    """Import multiple matches from osu! mp link URLs.

    Args:
        db: MatchDatabase instance
        urls: List of osu! mp links
        pool_id: Optional pool identifier (shared across all matches)
        round_name: Optional round name (shared across all matches)

    Returns:
        List of database match_ids for successfully imported matches
    """
    from ..client import make_client

    results: list[int] = []

    async with make_client() as client:
        for url in urls:
            mp_link = parse_mp_link(url)
            if mp_link is None:
                logger.error("Invalid mp link: %s", url)
                continue

            try:
                imported = await fetch_mp_match(client, mp_link)
            except Exception:
                logger.exception("Failed to fetch match from %s", url)
                continue

            if not imported.games:
                logger.warning("No games found in match %d", mp_link.match_id)
                continue

            try:
                mid = await save_imported_match_with_pp(db, imported, pool_id=pool_id, round_name=round_name)
                results.append(mid)
                logger.info("Imported match %d -> db id %d (%d games)",
                           mp_link.match_id, mid, len(imported.games))
            except Exception:
                logger.exception("Failed to save match %d", mp_link.match_id)

    return results
