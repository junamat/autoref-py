from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from ..enums import Step
from .pool import Pool
from .ruleset import Ruleset
from .team import Team


class Match:
    _STATUS_COLUMNS = ["turn", "team_index", "step", "beatmap_id", "timestamp"]

    def __init__(
        self,
        ruleset: Ruleset,
        pool: Pool,
        next_step: Callable[[pd.DataFrame], tuple[int, Step]],
        *teams: Team,
        pool_id: str | None = None,
        round_name: str | None = None,
    ):
        self.ruleset = ruleset
        self.pool = pool
        self.next_step = next_step
        self.teams = teams
        self.match_status = pd.DataFrame(columns=self._STATUS_COLUMNS)
        self.match_id: int | None = None
        self.pool_id = pool_id
        self.round_name = round_name
        self.game_scores: list[tuple[int, int, list[dict]]] = []

    def add_game_scores(self, turn: int, beatmap_id: int, scores: list[dict]) -> None:
        self.game_scores.append((turn, beatmap_id, scores))

    def record_action(self, team_index: int, step: Step, beatmap_id: int) -> None:
        row = {
            "turn": len(self.match_status),
            "team_index": team_index,
            "step": step.name,
            "beatmap_id": beatmap_id,
            "timestamp": pd.Timestamp.now(),
        }
        self.match_status = pd.concat(
            [self.match_status, pd.DataFrame([row])],
            ignore_index=True,
        )

    def save(self, path: str | Path) -> None:
        self.match_status.to_csv(path, index=False)

    def resume(self, path: str | Path) -> None:
        self.match_status = pd.read_csv(path, parse_dates=["timestamp"])
