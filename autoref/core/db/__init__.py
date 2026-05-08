from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .connection import connect
from .migrations import run_migrations
from .repos import ActionRepo, LiveRepo, MatchRepo, ScoreRepo, TeamRepo

if TYPE_CHECKING:
    from ..models import Match

__all__ = ["MatchDatabase"]


class MatchDatabase:
    def __init__(self, path: str | Path = "matches.db") -> None:
        self._conn = connect(path)
        run_migrations(self._conn)
        self.matches = MatchRepo(self._conn)
        self.actions = ActionRepo(self._conn)
        self.scores  = ScoreRepo(self._conn)
        self.teams   = TeamRepo(self._conn)
        self.live    = LiveRepo(self._conn)

    # ---------------------------------------------------------------- orchestrators

    def save_match(self, match: "Match",
                   winner_team_index: int | None = None) -> int:
        ruleset_mults = getattr(match.ruleset, "score_multipliers", None)
        mults_by_bid: dict[int, dict[str, float]] = {}
        try:
            for pm in match.pool.flatten():
                mults_by_bid[int(pm.beatmap_id)] = pm.effective_multipliers(ruleset_mults)
        except Exception:
            mults_by_bid = {}

        mid = self.matches.save_match_row(match, winner_team_index)
        for i, team in enumerate(match.teams):
            self.teams.insert_team(mid, i, team.name)
        self.actions.insert_actions(mid, match.match_status)
        self.scores.insert_scores(mid, getattr(match, "game_scores", []), mults_by_bid)

        self._conn.commit()
        match.match_id = mid
        return mid

    def get_leaderboard(self, *, method: str = "zscore", include=None,
                        aggregate: str = "sum",
                        pool_id: str | None = None,
                        round_name: str | None = None) -> pd.DataFrame:
        from ..stats import include_all, leaderboard
        return leaderboard(
            self.scores.all_with_team(pool_id=pool_id, round_name=round_name),
            method=method,
            include=include or include_all,
            aggregate=aggregate,
        )

    def get_z_sum_leaderboard(self, *, include=None) -> pd.DataFrame:
        return self.get_leaderboard(method="zscore", include=include)

    # ---------------------------------------------------------------- backward-compat delegates

    def get_match_history(self) -> pd.DataFrame:
        return self.matches.history()

    def get_filter_options(self) -> dict:
        return self.matches.filter_options()

    def get_pick_actions(self, *, pool_id: str | None = None,
                         round_name: str | None = None) -> pd.DataFrame:
        return self.actions.pick_actions(pool_id=pool_id, round_name=round_name)

    def get_map_stats(self, *, pool_id: str | None = None,
                      round_name: str | None = None) -> pd.DataFrame:
        return self.actions.map_stats(pool_id=pool_id, round_name=round_name)

    def get_map_action_breakdown(self, *, pool_id: str | None = None,
                                  round_name: str | None = None) -> pd.DataFrame:
        return self.actions.map_action_breakdown(pool_id=pool_id, round_name=round_name)

    def get_game_scores(self, match_id: int) -> pd.DataFrame:
        return self.scores.by_match(match_id)

    def get_all_scores(self, *, pool_id: str | None = None,
                       round_name: str | None = None) -> pd.DataFrame:
        return self.scores.all_with_team(pool_id=pool_id, round_name=round_name)

    def update_pp_bulk(self,
                       updates: list[tuple[int, float | None, str | None]]) -> int:
        return self.scores.update_pp_bulk(updates)

    def get_team_stats(self) -> pd.DataFrame:
        return self.teams.stats()

    def upsert_live_match(self, match_id: str, **kw) -> None:  # type: ignore[override]
        self.live.upsert(match_id, **kw)

    def update_live_match_status(self, match_id: str, status: str) -> None:
        self.live.update_status(match_id, status)

    def get_orphaned_live_matches(self) -> list[dict]:
        return self.live.get_orphaned()

    def prune_finished_live_matches(self, *, days: int = 7) -> int:
        return self.live.prune_finished(days=days)

    # ---------------------------------------------------------------- private (kept for tests that access it)

    def _match_filter(self, pool_id: str | None, round_name: str | None,
                      alias: str = "") -> tuple[str, list]:
        from .repos.base import match_filter
        return match_filter(pool_id, round_name, alias)

    # ---------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MatchDatabase":
        return self

    def __exit__(self, *_) -> None:
        self.close()
