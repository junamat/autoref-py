from __future__ import annotations

import aiosu

from ..enums import WinCondition
from .scheme import OrderScheme


class Ruleset:
    def __init__(
        self,
        vs: int,
        gamemode: aiosu.models.Gamemode,
        win_condition: WinCondition = WinCondition.SCORE_V2,
        enforced_mods: str = "NF",
        team_mode: int = 2,
        best_of: int = 1,
        bans_per_team: "int | list[int]" = 0,
        protects_per_team: "int | list[int]" = 0,
        schemes: "list[OrderScheme] | None" = None,
        score_multipliers: dict[str, float] | None = None,
    ):
        self.vs = vs
        self.gamemode = gamemode
        self.win_condition = win_condition
        self.enforced_mods = aiosu.models.mods.Mods(enforced_mods) if enforced_mods else None
        self.team_mode = team_mode
        self.best_of = best_of
        self.bans_per_team = bans_per_team
        self.protects_per_team = protects_per_team
        self.schemes = schemes
        self.score_multipliers = score_multipliers

    @property
    def wins_needed(self) -> int:
        return self.best_of // 2 + 1

    def bans_for(self, team_index: int) -> int:
        v = self.bans_per_team
        return v if isinstance(v, int) else v[team_index]

    def protects_for(self, team_index: int) -> int:
        v = self.protects_per_team
        return v if isinstance(v, int) else v[team_index]
