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
    """SQLite persistence layer for autoref match data.

    Wraps a single SQLite connection and runs schema migrations on init.
    Exposes typed repo objects (matches, actions, scores, teams, live) plus
    higher-level orchestrators for common multi-table operations.
    """

    def __init__(self, path: str | Path = "matches.db") -> None:
        """Open (or create) the database at path and run all pending migrations.

        Args:
            path: Filesystem path to the SQLite file. Created if absent.
        """
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
        """Persist a completed match and return its auto-assigned integer ID.

        Writes match, team, action, and score rows in a single transaction.
        Sets match.match_id in-place.

        Args:
            match: Completed Match instance to persist.
            winner_team_index: 0-based winning team index, or None for draw/unfinished.

        Returns:
            Auto-assigned match ID (also stored on match.match_id).
        """
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
        """Compute and return a player leaderboard.

        Args:
            method: Scoring method key (e.g. "zscore", "avg_score"). Defaults to "zscore".
            include: Row-filter predicate; defaults to include_all.
            aggregate: Per-player score aggregation ("sum" or "avg"). Defaults to "sum".
            pool_id: Restrict to matches with this pool ID.
            round_name: Restrict to matches with this round name.

        Returns:
            DataFrame with players ranked by the chosen method.
        """
        from ..stats import include_all, leaderboard
        return leaderboard(
            self.scores.all_with_team(pool_id=pool_id, round_name=round_name),
            method=method,
            include=include or include_all,
            aggregate=aggregate,
        )

    def get_z_sum_leaderboard(self, *, include=None) -> pd.DataFrame:
        """Compute a z-score sum leaderboard. Shortcut for get_leaderboard(method='zscore')."""
        return self.get_leaderboard(method="zscore", include=include)

    # ---------------------------------------------------------------- backward-compat delegates

    def get_match_history(self) -> pd.DataFrame:
        """Return all saved matches as a DataFrame."""
        return self.matches.history()

    def get_filter_options(self) -> dict:
        """Return distinct pool_id and round_name values for UI filter dropdowns."""
        return self.matches.filter_options()

    def get_pick_actions(self, *, pool_id: str | None = None,
                         round_name: str | None = None) -> pd.DataFrame:
        """Return all pick actions, optionally filtered by pool or round."""
        return self.actions.pick_actions(pool_id=pool_id, round_name=round_name)

    def get_map_stats(self, *, pool_id: str | None = None,
                      round_name: str | None = None) -> pd.DataFrame:
        """Return per-map pick/ban/protect counts."""
        return self.actions.map_stats(pool_id=pool_id, round_name=round_name)

    def get_map_action_breakdown(self, *, pool_id: str | None = None,
                                  round_name: str | None = None) -> pd.DataFrame:
        """Return per-map action breakdown with win rates."""
        return self.actions.map_action_breakdown(pool_id=pool_id, round_name=round_name)

    def get_game_scores(self, match_id: int) -> pd.DataFrame:
        """Return all game scores for a single match.

        Args:
            match_id: Integer match ID.
        """
        return self.scores.by_match(match_id)

    def get_all_scores(self, *, pool_id: str | None = None,
                       round_name: str | None = None) -> pd.DataFrame:
        """Return all game scores joined with team data, optionally filtered."""
        return self.scores.all_with_team(pool_id=pool_id, round_name=round_name)

    def update_pp_bulk(self,
                       updates: list[tuple[int, float | None, str | None]]) -> int:
        """Bulk-update pp values on score rows.

        Args:
            updates: List of (score_id, pp_value, pp_version) tuples.
                None pp_value marks a failed compute (leaves NULL for retry).

        Returns:
            Number of rows updated.
        """
        return self.scores.update_pp_bulk(updates)

    def get_team_stats(self) -> pd.DataFrame:
        """Return per-team win/loss statistics."""
        return self.teams.stats()

    def upsert_live_match(self, match_id: str, **kw) -> None:  # type: ignore[override]
        """Insert or update a live_matches row by match_id."""
        self.live.upsert(match_id, **kw)

    def update_live_match_status(self, match_id: str, status: str) -> None:
        """Update the status column of a live_matches row.

        Args:
            match_id: UUID-prefix match identifier.
            status: New status value (pending/running/orphaned/finished/crashed).
        """
        self.live.update_status(match_id, status)

    def get_orphaned_live_matches(self) -> list[dict]:
        """Return all live_matches rows with status in {'running', 'orphaned'}."""
        return self.live.get_orphaned()

    def prune_finished_live_matches(self, *, days: int = 7) -> int:
        """Delete finished live_matches rows older than days.

        Args:
            days: Retention window; rows older than this are deleted. Defaults to 7.

        Returns:
            Number of rows deleted.
        """
        return self.live.prune_finished(days=days)

    # ---------------------------------------------------------------- private (kept for tests that access it)

    def _match_filter(self, pool_id: str | None, round_name: str | None,
                      alias: str = "") -> tuple[str, list]:
        from .repos.base import match_filter
        return match_filter(pool_id, round_name, alias)

    # ---------------------------------------------------------------- lifecycle

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> "MatchDatabase":
        return self

    def __exit__(self, *_) -> None:
        self.close()
