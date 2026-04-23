"""
Qualifiers PoC — runs a solo qualifiers lobby for junamat.
Usage: python run_qualifiers.py
Requires .env with BANCHO_USERNAME, BANCHO_PASSWORD, CLIENT_ID, CLIENT_SECRET
"""
import asyncio
from dotenv import load_dotenv
from os import getenv

import bancho

from autoref.models import Match, ModdedPool, PlayableMap, Pool, Ruleset, Team, Timers
from autoref.enums import WinCondition
from autoref.qualifiers import QualifiersAutoRef

load_dotenv()

import aiosu

POOL = Pool("Qualifiers",
    ModdedPool("NM", aiosu.models.mods.Mods("NF"),
        PlayableMap(1725575, name="NM1"),
        PlayableMap(2831724, name="NM2"),
        PlayableMap(2302096, name="NM3"),
        PlayableMap(2531431, name="NM4"),
    ),
    ModdedPool("HD", aiosu.models.mods.Mods("HDNF"),
        PlayableMap(637391,  name="HD1"),
        PlayableMap(1313278, name="HD2"),
    ),
    ModdedPool("HR", aiosu.models.mods.Mods("HRNF"),
        PlayableMap(1427203, name="HR1"),
        PlayableMap(181589,  name="HR2"),
    ),
    ModdedPool("DT", aiosu.models.mods.Mods("DTNF"),
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
    between_maps=10,
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

    match = Match(RULESET, POOL, lambda _: (0, None), team)  # next_step overridden by QualifiersAutoRef

    ar = QualifiersAutoRef(
        client=client,
        match=match,
        room_name="autoref-py qualifiers PoC",
        runs=1,
        timers=TIMERS,
    )

    print("Connecting to Bancho...")
    await client.connect()
    print("Connected. Starting qualifiers...")
    await ar.run()
    print("Done.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
