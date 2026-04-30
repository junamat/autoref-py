"""Tests for Z-Sum leaderboard math + predicate modularity."""
import math

import pandas as pd
import pytest

from autoref.core.stats import (
    exclude_failed, include_all, z_sum_leaderboard,
    leaderboard, avg_score_leaderboard, avg_placements_leaderboard,
    percentile_leaderboard, zipf_leaderboard, pct_diff_leaderboard,
    METHODS,
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


def test_missing_score_counts_as_zero():
    """Missing scores: avg_score counts as 0, Z-Sum/Zipf exclude them."""
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 10},
        {"user_id": 2, "score": 100, "beatmap_id": 10},
        {"user_id": 1, "score": 200, "beatmap_id": 20},
        # user 2 has no score on map 20
    ])
    
    # Z-Sum: missing scores excluded, so user 2 only has 1 map
    z_out = z_sum_leaderboard(df).set_index("user_id")
    assert z_out.loc[1, "maps_played"] == 2
    assert z_out.loc[2, "maps_played"] == 1
    
    # avg_score: missing scores counted as 0, so both have 2 maps
    avg_out = avg_score_leaderboard(df).set_index("user_id")
    assert avg_out.loc[1, "maps_played"] == 2
    assert avg_out.loc[2, "maps_played"] == 2
    # user 1: (200+200)/2 = 200, user 2: (100+0)/2 = 50
    assert avg_out.loc[1, "avg_score"] == pytest.approx(200.0)
    assert avg_out.loc[2, "avg_score"] == pytest.approx(50.0)


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

# --------------------------------------------------------- real-data regression

def test_matches_4wc_qualifiers_spreadsheet():
    """Sanity check against a published qualifiers sheet (376 scores, 15 players).

    Fixture sourced from:
      https://docs.google.com/spreadsheets/d/1_rBb5XkPcgrqPer083qlTJiDyNUwf3-KC0CL2DrIo78
      tab `_filtered_scores` (raw input) + `Qualifiers Results` (expected z-sum).

    Sheet config: calculation=Z-Sum, score_aggregate=Max, count_failed=True
    → matches our defaults (include_all + best score per (player, map)).
    Uses `modded_score` because the sheet feeds that into Z-Sum, not raw `score`
    (mod multipliers applied upstream; for this stage they're all 1.0 except 1.06).
    """
    from pathlib import Path
    fixtures = Path(__file__).parent / "fixtures"
    scores = pd.read_csv(fixtures / "qualifiers_4wc_scores.csv")
    expected = pd.read_csv(fixtures / "qualifiers_4wc_expected.csv")

    df = scores.rename(columns={"score": "raw_score", "modded_score": "score"})
    out = z_sum_leaderboard(df).head(15)

    cmp = out.merge(expected, on="username", how="left")
    # Every row must agree with the sheet to ≤1e-9.
    assert cmp["z_sum_sheet"].notna().all(), "missing expected row(s)"
    delta = (cmp["z_sum"] - cmp["z_sum_sheet"]).abs().max()
    assert delta < 1e-9, f"max |delta| was {delta}"

    # And the leaderboard order must match.
    assert list(out["username"])[:15] == list(expected["username"])[:15]


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


# --------------------------------------------------------- new calculation methods

def test_methods_registry_has_all_keys():
    assert set(METHODS) == {"zscore", "avg_score", "placements", "percentile", "zipf", "pct_diff"}


def test_leaderboard_dispatcher_unknown_method():
    df = _scores([{"user_id": 1, "score": 100, "beatmap_id": 1}])
    with pytest.raises(ValueError, match="unknown method"):
        leaderboard(df, method="nope")


def test_leaderboard_dispatcher_routes_to_zscore():
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 1},
        {"user_id": 2, "score": 100, "beatmap_id": 1},
    ])
    assert leaderboard(df, method="zscore").equals(z_sum_leaderboard(df))


# avg_score

def test_avg_score_two_players():
    df = _scores([
        {"user_id": 1, "score": 300, "beatmap_id": 1},
        {"user_id": 1, "score": 100, "beatmap_id": 2},
        {"user_id": 2, "score": 200, "beatmap_id": 1},
        {"user_id": 2, "score": 200, "beatmap_id": 2},
    ])
    out = avg_score_leaderboard(df).set_index("user_id")
    assert out.loc[1, "avg_score"] == pytest.approx(200.0)
    assert out.loc[2, "avg_score"] == pytest.approx(200.0)


def test_avg_score_sorted_desc():
    df = _scores([
        {"user_id": 1, "score": 100, "beatmap_id": 1},
        {"user_id": 2, "score": 500, "beatmap_id": 1},
    ])
    out = avg_score_leaderboard(df)
    assert out.iloc[0]["user_id"] == 2


# placements

def test_placements_rank_order():
    df = _scores([
        {"user_id": 1, "score": 300, "beatmap_id": 1},
        {"user_id": 2, "score": 200, "beatmap_id": 1},
        {"user_id": 3, "score": 100, "beatmap_id": 1},
    ])
    out = avg_placements_leaderboard(df).set_index("user_id")
    # user 1 = rank 1, user 2 = rank 2, user 3 = rank 3
    assert out.loc[1, "placement_sum"] == pytest.approx(1.0)
    assert out.loc[3, "placement_sum"] == pytest.approx(3.0)


def test_placements_sorted_ascending():
    df = _scores([
        {"user_id": 1, "score": 100, "beatmap_id": 1},
        {"user_id": 2, "score": 500, "beatmap_id": 1},
    ])
    out = avg_placements_leaderboard(df)
    # lower placement_sum = better → user 2 (rank 1) first
    assert out.iloc[0]["user_id"] == 2


# percentile

def test_percentile_top_player_near_100():
    df = _scores([
        {"user_id": 1, "score": 300, "beatmap_id": 1},
        {"user_id": 2, "score": 200, "beatmap_id": 1},
        {"user_id": 3, "score": 100, "beatmap_id": 1},
    ])
    out = percentile_leaderboard(df).set_index("user_id")
    assert out.loc[1, "percentile_sum"] > out.loc[2, "percentile_sum"]
    assert out.loc[2, "percentile_sum"] > out.loc[3, "percentile_sum"]


# zipf

def test_zipf_rank1_gets_weight_1():
    df = _scores([
        {"user_id": 1, "score": 300, "beatmap_id": 1},
        {"user_id": 2, "score": 100, "beatmap_id": 1},
    ])
    out = zipf_leaderboard(df).set_index("user_id")
    # correction = 1.4 * 1 map = 1.4
    # user 1: rank 1 → 100/(1+1.4) = 100/2.4 ≈ 41.67
    # user 2: rank 2 → 100/(2+1.4) = 100/3.4 ≈ 29.41
    assert out.loc[1, "zipf_sum"] == pytest.approx(100.0 / 2.4)
    assert out.loc[2, "zipf_sum"] == pytest.approx(100.0 / 3.4)


# pct_diff

def test_pct_diff_above_mean_is_positive():
    df = _scores([
        {"user_id": 1, "score": 200, "beatmap_id": 1},
        {"user_id": 2, "score": 100, "beatmap_id": 1},
    ])
    out = pct_diff_leaderboard(df).set_index("user_id")
    # min=100, max=200; user1: (200-100)/(200-100)*100 = 100; user2: (100-100)/(200-100)*100 = 0
    assert out.loc[1, "pct_diff_sum"] == pytest.approx(100.0)
    assert out.loc[2, "pct_diff_sum"] == pytest.approx(0.0)


def test_pct_diff_single_player_zero():
    df = _scores([{"user_id": 1, "score": 500, "beatmap_id": 1}])
    out = pct_diff_leaderboard(df)
    # Single player: min == max, fillna(0.5) * 100 = 50
    assert out.iloc[0]["pct_diff_sum"] == pytest.approx(50.0)


# get_leaderboard via MatchDatabase

def test_get_leaderboard_method_param():
    from autoref.core.storage import MatchDatabase
    db = MatchDatabase(":memory:")
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
    for method in METHODS:
        out = db.get_leaderboard(method=method)
        assert not out.empty, f"method={method} returned empty"
        assert "user_id" in out.columns
