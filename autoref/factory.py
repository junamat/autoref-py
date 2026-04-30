"""Factory: build an AutoRef instance from a plain dict payload.

Usable from the web server, CLI, Discord, or tests — no web dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def flatten_pool_tree(nodes: list, parent_mods: str = "") -> list:
    """Flatten a pool-builder tree into the flat map-entry list build_autoref expects."""
    entries = []
    for node in nodes:
        if node.get("type") == "map":
            entries.append({
                "beatmap_id":   node.get("bid", ""),
                "name":         node.get("code") or node.get("name", ""),
                "mod_group":    node.get("code", "MAP").rstrip("0123456789") or "NM",
                "mods":         node.get("mods") or parent_mods,
                "is_tiebreaker": node.get("tb", False),
            })
        elif node.get("children"):
            entries.extend(flatten_pool_tree(node["children"], node.get("mods") or parent_mods))
    return entries


async def build_autoref(payload: dict, bancho_username: str = "", bancho_password: str = "",
                        pool_loader=None, db=None):
    """Build and return an (AutoRef, BanchoClient) pair from a web/CLI payload dict.

    payload keys:
        type            "bracket" | "qualifiers"
        room_name       str
        mode            "off" | "assisted" | "auto"
        best_of         int
        bans_per_team   int
        protects_per_team int
        teams           [{"name": str, "players": [str, ...]}, ...]
        maps            [{"beatmap_id", "name", "mod_group", "mods", "is_tiebreaker"}, ...]
        pool_id         str  (alternative to maps; loaded via pool_loader(id) -> saved pool dict)
        round_name      str  (optional tournament round, e.g. "RO16", "QF", "Grand Finals")

    pool_loader: optional callable(pool_id) -> saved pool dict (with "tree" key).
    """
    import bancho as bancho_lib
    import aiosu
    from .core.models import Match, Pool, PlayableMap, ModdedPool, Ruleset, Team, OrderScheme
    from .core.enums import WinCondition, RefMode, Step
    from .core.score_fetcher import ScoreFetcher
    from .client import make_client
    from .controllers.bracket import BracketAutoRef
    from .controllers.qualifiers import QualifiersAutoRef

    match_type = payload.get("type", "bracket")
    room_name  = payload.get("room_name", "autoref match")
    mode       = RefMode(payload.get("mode", "off"))
    best_of    = int(payload.get("best_of", 1))
    bans       = int(payload.get("bans_per_team", 0))
    protects   = int(payload.get("protects_per_team", 0))

    # Resolve map entries — from inline list or saved pool
    map_entries = payload.get("maps", [])
    pool_id = payload.get("pool_id")
    if pool_id and pool_loader:
        saved = pool_loader(pool_id)
        if saved:
            map_entries = flatten_pool_tree(saved.get("tree", []))

    # Build pool
    groups: dict[str, list] = {}
    for e in map_entries:
        groups.setdefault(e.get("mod_group", "NM"), []).append(e)

    pool_children = []
    for group_name, entries in groups.items():
        mods_str = entries[0].get("mods", "") if entries else ""
        maps = [PlayableMap(
            int(e["beatmap_id"]),
            name=e.get("name") or f"{group_name}{i+1}",
            is_tiebreaker=e.get("is_tiebreaker", False),
        ) for i, e in enumerate(entries)]
        if mods_str and mods_str.lower() not in ("", "nm", "nomod"):
            mods_val = "Freemod" if mods_str.lower() == "freemod" else aiosu.models.mods.Mods(mods_str)
            pool_children.append(ModdedPool(group_name, mods_val, *maps))
        else:
            pool_children.append(Pool(group_name, *maps))

    pool = Pool(room_name, *pool_children)

    # Build teams
    team_defs = payload.get("teams", [{"name": "Team 1"}, {"name": "Team 2"}])
    teams = []
    for td in team_defs:
        t = Team(td["name"])
        t.players = [type("Player", (), {"username": p})() for p in td.get("players", [])]
        teams.append(t)

    total_players = sum(len(t.players) for t in teams) or int(payload.get("vs", 1))

    ruleset = Ruleset(
        vs=total_players if match_type == "qualifiers" else int(payload.get("vs", 1)),
        gamemode=aiosu.models.Gamemode.STANDARD,
        win_condition=WinCondition.SCORE_V2,
        enforced_mods="NF",
        team_mode=0 if match_type == "qualifiers" else 2,
        best_of=best_of,
        bans_per_team=bans,
        protects_per_team=protects,
        schemes=[OrderScheme("standard", ban_pattern="ABBA")] if match_type == "bracket" else None,
    )

    match = Match(
        ruleset, pool, lambda _: (0, Step.FINISH), *teams,
        pool_id=payload.get("pool_id"),
        round_name=(payload.get("round_name") or payload.get("round") or None),
    )
    client = bancho_lib.BanchoClient(username=bancho_username, password=bancho_password)

    # API-side score enrichment. AutoRef.run() will aclose the fetcher when the match ends.
    fetcher: ScoreFetcher | None = None
    try:
        fetcher = ScoreFetcher(make_client())
    except Exception:
        logger.exception("could not build ScoreFetcher; continuing without enrichment")

    if match_type == "qualifiers":
        ar = QualifiersAutoRef(client=client, match=match, room_name=room_name,
                               mode=mode, score_fetcher=fetcher, db=db)
    else:
        ar = BracketAutoRef(client=client, match=match, room_name=room_name,
                            mode=mode, score_fetcher=fetcher, db=db)

    return ar, client
