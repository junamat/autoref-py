"""
Qualifiers PoC — runs a solo qualifiers lobby for junamat.
Usage: python run_qualifiers.py
Requires .env with BANCHO_USERNAME, BANCHO_PASSWORD, CLIENT_ID, CLIENT_SECRET
"""
import asyncio
import logging
from dotenv import load_dotenv
from os import getenv

logging.basicConfig(level=logging.INFO, format="%(message)s")

import bancho

from autoref import Match, ModdedPool, PlayableMap, Pool, Ruleset, Team, Timers
from autoref import WinCondition, RefMode, Step
from autoref import QualifiersAutoRef
from autoref import WebInterface, WebServer

load_dotenv()

import aiosu

POOL = Pool("Qualifiers",
    Pool("NM",
        PlayableMap(1725575, name="NM1"),
        PlayableMap(2831724, name="NM2"),
        PlayableMap(2302096, name="NM3"),
        PlayableMap(2531431, name="NM4"),
    ),
    ModdedPool("HD", aiosu.models.mods.Mods("HD"),
        PlayableMap(637391,  name="HD1"),
        PlayableMap(1313278, name="HD2"),
    ),
    ModdedPool("HR", aiosu.models.mods.Mods("HR"),
        PlayableMap(1427203, name="HR1"),
        PlayableMap(181589,  name="HR2"),
    ),
    ModdedPool("DT", aiosu.models.mods.Mods("DT"),
        PlayableMap(96525,   name="DT1"),
        PlayableMap(2035004, name="DT2"),
    ),
)

RULESET = Ruleset(
    vs=1,
    gamemode=aiosu.models.Gamemode.STANDARD,
    win_condition=WinCondition.SCORE_V2,
    enforced_mods="NF",
    team_mode=0,  # HeadToHead
)

TIMERS = Timers(
    between_maps=90,
    ready_up=60,
    force_start=10,
)


async def main():
    client = bancho.BanchoClient(
        username=getenv("BANCHO_USERNAME"),
        password=getenv("BANCHO_PASSWORD"),
    )

    team = Team("junamat")
    team.players = [type("Player", (), {"username": "junamat"})()]

    match = Match(RULESET, POOL, lambda _: (0, Step.WIN), team)  # next_step overridden by QualifiersAutoRef

    mode = RefMode(getenv("AUTOREF_MODE", "auto").lower())
    prefix = getenv("AUTOREF_PREFIX", ">")
    refs_env = getenv("AUTOREF_REFS", "")
    refs = {r.strip() for r in refs_env.split(",") if r.strip()} or None

    ar = QualifiersAutoRef(
        client=client,
        match=match,
        room_name="autoref-py qualifiers PoC",
        runs=1,
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
    print("Connecting to Bancho...")
    await client.connect()
    print("Connected. Starting qualifiers on http://localhost:8080 ...")
    await asyncio.gather(server.start(), ar.run())
    print("Done.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
