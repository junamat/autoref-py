from __future__ import annotations

import asyncio

import aiosu
import pandas as pd


class Team:
    def __init__(self, name: str):
        self.name = name
        self.players: list = []

    @classmethod
    async def create(cls, name: str, *player_ids: int,
                     client: "aiosu.v2.Client | None" = None) -> "Team":
        instance = cls(name)
        if client is not None:
            results = await asyncio.gather(
                *(client.get_user(pid) for pid in player_ids)
            )
        else:
            from ...client import make_client
            async with make_client() as c:
                results = await asyncio.gather(
                    *(c.get_user(pid) for pid in player_ids)
                )
        instance.players = list(results)
        return instance

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(p) for p in self.players])
