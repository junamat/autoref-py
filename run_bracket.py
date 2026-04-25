"""
Bracket PoC — runs a BO13 1v1 Finals match.
Usage: python run_bracket.py
Requires .env with BANCHO_USERNAME, BANCHO_PASSWORD, CLIENT_ID, CLIENT_SECRET
         and optionally TEAM_RED_PLAYER, TEAM_BLUE_PLAYER (osu! usernames).
"""
import asyncio
import logging
from dotenv import load_dotenv
from os import getenv

logging.basicConfig(level=logging.INFO, format="%(message)s")

import bancho

from autoref import Match, ModdedPool, OrderScheme, PlayableMap, Pool, Ruleset, Team, Timers
from autoref import WinCondition, RefMode, Step
from autoref import BracketAutoRef
from autoref import WebInterface, WebServer

load_dotenv()

import aiosu

# --------------------------------------------------------------------------- pool
POOL = Pool("Finals",
    Pool("NM",
        PlayableMap(4061078, name="NM1"),
        PlayableMap(3709956, name="NM2"),
        PlayableMap(4151262, name="NM3"),
        PlayableMap(3774312, name="NM4"),
        PlayableMap(2109448, name="NM5"),
        PlayableMap(3694974, name="NM6"),
    ),
    ModdedPool("HD", aiosu.models.mods.Mods("HD"),
        PlayableMap(3876766, name="HD1"),
        PlayableMap(2223544, name="HD2"),
        PlayableMap(3879312, name="HD3"),
    ),
    ModdedPool("HR", aiosu.models.mods.Mods("HR"),
        PlayableMap(3978413, name="HR1"),
        PlayableMap(2713278, name="HR2"),
        PlayableMap(4053727, name="HR3"),
    ),
    ModdedPool("DT", aiosu.models.mods.Mods("DT"),
        PlayableMap(4148369, name="DT1"),
        PlayableMap(1744010, name="DT2"),
        PlayableMap(1927444, name="DT3"),
        PlayableMap(4007189, name="DT4"),
    ),
    ModdedPool("FM", aiosu.models.mods.Mods("Freemod"),
        PlayableMap(4147399, name="FM1"),
        PlayableMap(3535202, name="FM2"),
    ),
    Pool("TB",
        PlayableMap(4151225, name="TB", is_tiebreaker=True),
    ),
)

# --------------------------------------------------------------------------- ruleset
SCHEME = OrderScheme(
    "standard",
    protect_first=0,   # roll winner protects first
    ban_first=0,       # roll winner bans first
    pick_first=0,      # roll winner picks first
    ban_pattern="ABBA",
)

RULESET = Ruleset(
    vs=1,
    gamemode=aiosu.models.Gamemode.STANDARD,
    win_condition=WinCondition.SCORE_V2,
    enforced_mods="NF",
    team_mode=0,  # HeadToHead
    best_of=13,
    bans_per_team=2,
    protects_per_team=1,
    schemes=[SCHEME],
)

TIMERS = Timers(
    between_maps=10,
    ready_up=60,
    force_start=10,
)


async def main():
    client = bancho.BanchoClient(
        username=getenv("BANCHO_USERNAME"),
        password=getenv("BANCHO_PASSWORD"),
    )

    red_player = getenv("TEAM_RED_PLAYER", "player1")
    blue_player = getenv("TEAM_BLUE_PLAYER", "player2")

    red = Team(red_player)
    red.players = [type("Player", (), {"username": red_player})()]
    blue = Team(blue_player)
    blue.players = [type("Player", (), {"username": blue_player})()]

    match = Match(RULESET, POOL, lambda _: (0, Step.WIN), red, blue)

    mode = RefMode(getenv("AUTOREF_MODE", "auto").lower())
    prefix = getenv("AUTOREF_PREFIX", ">")
    refs_env = getenv("AUTOREF_REFS", "")
    refs = {r.strip() for r in refs_env.split(",") if r.strip()} or None

    ar = BracketAutoRef(
        client=client,
        match=match,
        room_name="autoref-py Finals",
        schemes=[SCHEME],
        timers=TIMERS,
        mode=mode,
        ref_prefix=prefix,
        refs=refs,
    )

    web = WebInterface()
    web.attach(ar.lobby)
    web.attach_autoref(ar)
    server = WebServer()
    server.register(web)

    print(f"Mode: {mode.value}  prefix: {prefix}  refs: {refs or '(any)'}")
    print(f"Red: {red_player}  Blue: {blue_player}")
    print("Connecting to Bancho...")
    await client.connect()
    print("Connected. Starting Finals on http://localhost:8080 ...")
    await asyncio.gather(server.start(), ar.run())
    print("Done.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
