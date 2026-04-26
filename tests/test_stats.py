"""Tests for Z-Sum leaderboard math + predicate modularity."""
import math

import pandas as pd
import pytest

from autoref.core.stats import (
    exclude_failed, include_all, z_sum_leaderboard,
)


def _scores(rows):
    """Build a game_scores-shaped DataFrame from a list of dicts.
    Missing fields default to neutral values."""
    cols = {"user_id", "username", "score", "passed", "beatmap_id"}
    out = []
    for r in rows:
        full = {"passed": True, "username": str(r.get("user_id"))}
        full.update(r)
        out.append(full)
    return pd.DataFrame(out)


# --------------------------------------------------------- shape + edge cases

def test_empty_df_returns_empty_leaderboard():
    df = pd.DataFrame(columns=["user_id", "username", "score", "passed", "beatmap_id"])
    out = z_sum_leaderboard(df)
    assert list(out.columns) == ["user_id", "username", "maps_played", "z_sum"]
    assert out.empty


def test_predicate_dropping_everything_returns_empty():
    df = _scores([
        {"user_id": 1, "score": 100, "beatmap_id": 1},
    ])
    out = z_sum_leaderboard(df, include=lambda r: False)
    assert out.empty


# --------------------------------------------------------- single-map math

def test_two_players_one_map():
    df = _scores([
        {"user_id": 1, "score": 100, "beatmap_id": 10},
        {"user_id": 2, "score": 200, "beatmap_id": 10},
    ])
    out = z_sum_leaderboard(df).set_index("user_id")
    # mean=150, sample std (ddof=1) = sqrt((50²+50²)/1) = sqrt(5000) ≈ 70.71
    expected = (200 - 150) / math.sqrt(5000)
    assert out.loc[2, "z_sum"] == pytest.approx(expected)
    assert out.loc[1, "z_sum"] == pytest.approx(-expected)
    assert out.loc[1, "maps_played"] == 1


def test_all_equal_scores_yield_zero_z():
    df = _scores([
        {"user_id": 1, "score": 500, "beatmap_id": 10},
        {"user_id": 2, "score": 500, "beatmap_id": 10},
    ])
    out = z_sum_leaderboard(df)
    assert (out["z_sum"] == 0).all()


def test_single_score_on_map_yields_zero_z():
    df = _scores([{"user_id": 1, "score": 1, "beatmap_id": 10}])
    out = z_sum_leaderboard(df)
    assert out.iloc[0]["z_sum"] == 0


# --------------------------------------------------------- multi-map sum

def test_z_sum_aggregates_across_maps():
    # Two maps, mean=150 std=√5000 on each. Player 1 above on both → z_sum = 2 * z.
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 10},
        {"user_id": 2, "score": 100, "beatmap_id": 10},
        {"user_id": 1, "score": 200, "beatmap_id": 20},
        {"user_id": 2, "score": 100, "beatmap_id": 20},
    ])
    out = z_sum_leaderboard(df).set_index("user_id")
    one_z = (200 - 150) / math.sqrt(5000)
    assert out.loc[1, "z_sum"] == pytest.approx(2 * one_z)
    assert out.loc[1, "maps_played"] == 2
    # leaderboard sorted desc → user 1 first.
    assert z_sum_leaderboard(df).iloc[0]["user_id"] == 1


# --------------------------------------------------------- best-of duplicates

def test_best_score_per_player_per_map():
    # Player 1 has two attempts on map 10; only the higher one should count.
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 10},
        {"user_id": 1, "score":  50, "beatmap_id": 10},
        {"user_id": 2, "score": 100, "beatmap_id": 10},
    ])
    out = z_sum_leaderboard(df).set_index("user_id")
    # Effective scores: 200 vs 100, mean=150, std=√5000
    expected = (200 - 150) / math.sqrt(5000)
    assert out.loc[1, "z_sum"] == pytest.approx(expected)


# --------------------------------------------------------- predicate modularity

def test_default_include_all_keeps_failed_scores():
    df = _scores([
        {"user_id": 1, "score": 999_999, "beatmap_id": 10, "passed": False},
        {"user_id": 2, "score": 100,     "beatmap_id": 10, "passed": True},
    ])
    out = z_sum_leaderboard(df, include=include_all).set_index("user_id")
    assert out.loc[1, "z_sum"] > 0
    assert out.loc[2, "z_sum"] < 0


def test_exclude_failed_drops_rows_before_stats():
    df = _scores([
        {"user_id": 1, "score": 999_999, "beatmap_id": 10, "passed": False},
        {"user_id": 2, "score": 200,     "beatmap_id": 10, "passed": True},
        {"user_id": 3, "score": 100,     "beatmap_id": 10, "passed": True},
    ])
    out = z_sum_leaderboard(df, include=exclude_failed)
    # Only users 2 and 3 remain; user 1 absent.
    assert set(out["user_id"]) == {2, 3}


def test_custom_predicate():
    """Arbitrary callable — e.g. only keep scores ≥ 150."""
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 10},
        {"user_id": 2, "score": 100, "beatmap_id": 10},
        {"user_id": 3, "score": 175, "beatmap_id": 10},
    ])
    out = z_sum_leaderboard(df, include=lambda r: r["score"] >= 150)
    assert set(out["user_id"]) == {1, 3}


# --------------------------------------------------------- integration with MatchDatabase

def test_get_z_sum_leaderboard_via_db():
    from autoref.core.storage import MatchDatabase
    db = MatchDatabase(":memory:")
    # Insert minimal rows directly. game_scores requires a match row to satisfy FK,
    # but sqlite does not enforce FKs unless PRAGMA is set, so this is fine.
    db._conn.execute(
        "INSERT INTO matches (ruleset_vs, gamemode, win_condition) VALUES (1, 'osu', 'SCORE_V2')"
    )
    rows = [
        (1, 0, 10, 100, "alpha", 0, 200, 0.95, 400, "[]", 1, 0, "S"),
        (1, 0, 10, 200, "beta",  1, 100, 0.90, 350, "[]", 1, 0, "A"),
    ]
    for r in rows:
        db._conn.execute(
            "INSERT INTO game_scores "
            "(match_id, turn, beatmap_id, user_id, username, team_index, "
            " score, accuracy, max_combo, mods, passed, perfect, rank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", r,
        )
    db._conn.commit()
    out = db.get_z_sum_leaderboard()
    assert len(out) == 2
    assert out.iloc[0]["user_id"] == 100  # higher score → higher z_sum → first
