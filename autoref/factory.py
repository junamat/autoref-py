"""Factory: build an AutoRef instance from a plain dict payload.

Usable from the web server, CLI, Discord, or tests — no web dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def flatten_pool_tree(nodes: list, parent_mods: str = "",
                      parent_mults_chain: list | None = None) -> list:
    """Flatten a pool-builder tree into the flat map-entry list expected by build_autoref.

    Pre-resolves effective per-map score multipliers by walking the tree and
    merging outer→inner→map dicts (most-specific wins per mod key).

    Args:
        nodes: Pool-tree node dicts; each has type="map" or children=[...].
        parent_mods: Mod string inherited from the parent pool node.
        parent_mults_chain: Accumulated score_multiplier dicts from ancestor nodes.

    Returns:
        Flat list of map-entry dicts with keys: beatmap_id, name, mod_group, mods,
        is_tiebreaker, score_multipliers.
    """
    entries = []
    chain = list(parent_mults_chain or [])
    for node in nodes:
        node_mults = node.get("score_multipliers")
        if node.get("type") == "map":
            merged: dict[str, float] = {}
            for d in chain:
                if d:
                    merged.update(d)
            if node_mults:
                merged.update(node_mults)
            entries.append({
                "beatmap_id":   node.get("bid", ""),
                "name":         node.get("code") or node.get("name", ""),
                "mod_group":    node.get("code", "MAP").rstrip("0123456789") or "NM",
                "mods":         node.get("mods") or parent_mods,
                "is_tiebreaker": node.get("tb", False),
                "score_multipliers": merged or None,
            })
        elif node.get("children"):
            sub_chain = chain + ([node_mults] if node_mults else [])
            entries.extend(flatten_pool_tree(node["children"],
                                             node.get("mods") or parent_mods,
                                             sub_chain))
    return entries


async def build_autoref(payload: dict, bancho_username: str = "", bancho_password: str = "",
                        pool_loader=None, db=None, defaults=None):
    """Build and return an (AutoRef, BanchoClient) pair from a web/CLI payload dict.

    Args:
        payload: Match configuration. Keys: type ("bracket"|"qualifiers"), room_name,
            mode ("off"|"assisted"|"auto"), best_of, bans_per_team, protects_per_team,
            teams ([{"name", "players"}]), maps ([{"beatmap_id", "name", "mod_group",
            "mods", "is_tiebreaker"}]), pool_id (alternative to maps), round_name.
        bancho_username: IRC username for the Bancho client.
        bancho_password: IRC password for the Bancho client.
        pool_loader: Optional callable(pool_id) -> saved pool dict with "tree" key.
        db: Optional MatchDatabase for match persistence.
        defaults: Optional Config supplying fallbacks (payload > defaults > builtin).

    Returns:
        Tuple of (AutoRef subclass instance, BanchoClient).
    """
    import aiosu
    import bancho as bancho_lib

    from .client import make_client
    from .controllers.bracket import BracketAutoRef
    from .controllers.qualifiers import QualifiersAutoRef
    from .core.enums import RefMode, Step, WinCondition
    from .core.models import Match, ModdedPool, OrderScheme, PlayableMap, Pool, Ruleset, Team
    from .core.score_fetcher import ScoreFetcher

    def _get(key, builtin, attr=None):
        """payload > defaults > builtin."""
        v = payload.get(key)
        if v is not None and v != "":
            return v
        if defaults is not None and attr:
            return getattr(defaults, attr, builtin)
        return builtin

    match_type = payload.get("type", "bracket")
    room_name  = payload.get("room_name", "autoref match")
    mode       = RefMode(_get("mode", "off", "default_mode"))
    best_of    = int(_get("best_of", 1, "default_best_of"))
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

    pool_children: list[Pool] = []
    for group_name, entries in groups.items():
        mods_str = entries[0].get("mods", "") if entries else ""
        maps = [PlayableMap(
            int(e["beatmap_id"]),
            name=e.get("name") or f"{group_name}{i+1}",
            is_tiebreaker=e.get("is_tiebreaker", False),
            score_multipliers=e.get("score_multipliers"),
        ) for i, e in enumerate(entries)]
        if mods_str and mods_str.lower() not in ("", "nm", "nomod"):
            mods_val = aiosu.models.mods.Mods([]) if mods_str.lower() == "freemod" else aiosu.models.mods.Mods(mods_str)
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

    from .core.models import Timers

    match = Match(
        ruleset, pool, lambda _: (0, Step.FINISH), *teams,
        pool_id=payload.get("pool_id"),
        round_name=(payload.get("round_name") or payload.get("round") or None),
    )
    client = bancho_lib.BanchoClient(username=bancho_username, password=bancho_password)

    ref_prefix = _get("prefix", ">", "default_prefix")
    refs_raw   = payload.get("refs") or (list(defaults.default_refs) if defaults else [])
    timers = Timers(
        pick=_get("timer_pick", 120, "timer_pick"),
        ban=_get("timer_ban", 120, "timer_ban"),
        protect=_get("timer_protect", 120, "timer_protect"),
        ready_up=_get("timer_ready_up", 90, "timer_ready_up"),
        start_map=_get("timer_start_map", 5, "timer_start_map"),
        force_start=_get("timer_force_start", 10, "timer_force_start"),
        between_maps=_get("timer_between_maps", 5, "timer_between_maps"),
        closing=_get("timer_closing", 30, "timer_closing"),
    )

    # API-side score enrichment. AutoRef.run() will aclose the fetcher when the match ends.
    fetcher: ScoreFetcher | None = None
    try:
        fetcher = ScoreFetcher(make_client())
    except Exception:
        logger.exception("could not build ScoreFetcher; continuing without enrichment")

    ar_kwargs = dict(client=client, match=match, room_name=room_name,
                     mode=mode, score_fetcher=fetcher, db=db,
                     timers=timers, ref_prefix=ref_prefix, refs=set(refs_raw) if refs_raw else None)
    ar: QualifiersAutoRef | BracketAutoRef
    if match_type == "qualifiers":
        ar = QualifiersAutoRef(**ar_kwargs)
    else:
        ar = BracketAutoRef(**ar_kwargs)

    return ar, client
