"""Smoke tests for autoref.plots — ensure each renderer returns non-empty bytes
for representative inputs and edge cases. Skipped if matplotlib/scipy aren't installed.
"""
import pandas as pd
import pytest

plots = pytest.importorskip("autoref.plots")


def _scores(rows):
    return pd.DataFrame(rows, columns=["user_id", "username", "beatmap_id", "score", "passed"])


def _map_stats(rows):
    return pd.DataFrame(rows, columns=["beatmap_id", "step", "count"])


def _is_png(b: bytes) -> bool:
    return b.startswith(b"\x89PNG\r\n\x1a\n")


def _is_svg(b: bytes) -> bool:
    return b.lstrip().startswith(b"<?xml") or b.lstrip().startswith(b"<svg")


# ── score_distribution ───────────────────────────────────────────────────────

def test_score_distribution_png():
    df = _scores([
        (1, "alice", 100, 800_000, 1),
        (2, "bob",   100, 850_000, 1),
        (3, "cara",  100, 900_000, 1),
        (4, "dan",   100, 920_000, 1),
        (5, "eli",   100, 880_000, 1),
        (6, "fae",   100, 830_000, 1),
        (7, "gus",   100, 50_000,  0),  # fail, filtered out
    ])
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)
    assert len(out) > 1000


def test_score_distribution_svg():
    df = _scores([(i, f"u{i}", 100, 700_000 + i * 1_000, 1) for i in range(20)])
    out = plots.score_distribution(df, beatmap_id=100, fmt="svg")
    assert _is_svg(out)


def test_score_distribution_empty_returns_image():
    df = _scores([])
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)  # placeholder image, not an exception


def test_score_distribution_single_score():
    df = _scores([(1, "alice", 100, 800_000, 1)])
    # n=1 → KDE skipped, hist still drawn; should not raise
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)


def test_score_distribution_zero_variance():
    df = _scores([(i, f"u{i}", 100, 800_000, 1) for i in range(5)])
    # all identical → std=0, KDE skipped; should not raise
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)


# ── pickban_heat ─────────────────────────────────────────────────────────────

def test_pickban_heat_png():
    df = _map_stats([
        (100, "PICK",    5),
        (100, "BAN",     2),
        (100, "PROTECT", 1),
        (101, "PICK",    3),
        (101, "BAN",     4),
        (102, "PROTECT", 2),
    ])
    out = plots.pickban_heat(df, fmt="png")
    assert _is_png(out)


def test_pickban_heat_empty():
    out = plots.pickban_heat(_map_stats([]), fmt="png")
    assert _is_png(out)


def test_pickban_heat_partial_columns():
    # only PICK actions present
    df = _map_stats([(100, "PICK", 5), (101, "PICK", 3)])
    out = plots.pickban_heat(df, fmt="png")
    assert _is_png(out)


# ── consistency_scatter ──────────────────────────────────────────────────────

def test_consistency_scatter_png():
    rows = []
    for uid in range(1, 6):
        for bid in (100, 101, 102):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000 + bid * 100, 1))
    out = plots.consistency_scatter(_scores(rows), fmt="png")
    assert _is_png(out)


def test_consistency_scatter_empty():
    out = plots.consistency_scatter(_scores([]), fmt="png")
    assert _is_png(out)


def test_consistency_scatter_svg():
    rows = [(uid, f"u{uid}", 100 + (uid % 3), 800_000 + uid * 1_000, 1) for uid in range(1, 11)]
    out = plots.consistency_scatter(_scores(rows), fmt="svg")
    assert _is_svg(out)


# ── registry ─────────────────────────────────────────────────────────────────

def test_registry_keys():
    assert set(plots.PLOTS) == {
        "score_distribution", "pickban_heat", "consistency_scatter",
        "tb_incidence", "map_close_factor", "pick_and_win_rate",
        "first_pick_frequency", "score_lead_trajectory", "comeback_rate",
        "action_sankey", "player_mod_radar", "team_rank_distribution",
        "pp_vs_score_scatter", "pp_consistency_scatter", "team_pool_heatmap",
        "team_strategy_profile", "team_score_variance", "score_inflation_curve",
        "mod_popularity_timeline", "fm_mod_combo_stack", "upset_rate_by_round",
    }


# ── tb_incidence ─────────────────────────────────────────────────────────────

def test_tb_incidence_empty():
    out = plots.tb_incidence(pd.DataFrame(columns=["pool_id", "total_matches", "tb_matches"]), fmt="png")
    assert _is_png(out)


def test_tb_incidence_png():
    df = pd.DataFrame([
        {"pool_id": "A", "total_matches": 20, "tb_matches": 5},
        {"pool_id": "B", "total_matches": 15, "tb_matches": 8},
    ])
    out = plots.tb_incidence(df, fmt="png")
    assert _is_png(out)


# ── map_close_factor ─────────────────────────────────────────────────────────

def test_map_close_factor_empty():
    out = plots.map_close_factor(pd.DataFrame(columns=["match_id", "beatmap_id", "team_index", "total_score"]), fmt="png")
    assert _is_png(out)


def test_map_close_factor_png():
    df = pd.DataFrame([
        {"match_id": 1, "beatmap_id": 100, "team_index": 0, "total_score": 800_000},
        {"match_id": 1, "beatmap_id": 100, "team_index": 1, "total_score": 790_000},
        {"match_id": 2, "beatmap_id": 100, "team_index": 0, "total_score": 850_000},
        {"match_id": 2, "beatmap_id": 100, "team_index": 1, "total_score": 820_000},
    ])
    out = plots.map_close_factor(df, fmt="png")
    assert _is_png(out)


def test_map_close_factor_ffa_empty():
    out = plots.map_close_factor(pd.DataFrame(columns=["beatmap_id", "score"]), fmt="png")
    assert _is_png(out)


def test_map_close_factor_ffa_png():
    df = pd.DataFrame([
        {"beatmap_id": 100, "score": 800_000},
        {"beatmap_id": 100, "score": 790_000},
        {"beatmap_id": 100, "score": 810_000},
        {"beatmap_id": 101, "score": 850_000},
        {"beatmap_id": 101, "score": 820_000},
        {"beatmap_id": 101, "score": 830_000},
    ])
    out = plots.map_close_factor(df, fmt="png")
    assert _is_png(out)


# ── pick_and_win_rate ────────────────────────────────────────────────────────

def test_pick_and_win_rate_empty():
    out = plots.pick_and_win_rate(pd.DataFrame(columns=["beatmap_id", "picks", "wins"]), fmt="png")
    assert _is_png(out)


def test_pick_and_win_rate_png():
    df = pd.DataFrame([
        {"beatmap_id": 100, "picks": 10, "wins": 7},
        {"beatmap_id": 101, "picks": 8, "wins": 3},
        {"beatmap_id": 102, "picks": 6, "wins": 4},
    ])
    out = plots.pick_and_win_rate(df, fmt="png")
    assert _is_png(out)


# ── first_pick_frequency ─────────────────────────────────────────────────────

def test_first_pick_frequency_empty():
    out = plots.first_pick_frequency(pd.DataFrame(columns=["match_id", "beatmap_id", "picker_team", "pool_id"]), fmt="png")
    assert _is_png(out)


def test_first_pick_frequency_png():
    df = pd.DataFrame([
        {"match_id": 1, "beatmap_id": 100, "picker_team": 0, "pool_id": "A"},
        {"match_id": 2, "beatmap_id": 100, "picker_team": 1, "pool_id": "A"},
        {"match_id": 3, "beatmap_id": 101, "picker_team": 0, "pool_id": "A"},
    ])
    out = plots.first_pick_frequency(df, fmt="png")
    assert _is_png(out)


# ── score_lead_trajectory ────────────────────────────────────────────────────

def test_score_lead_trajectory_empty():
    out = plots.score_lead_trajectory(pd.DataFrame(columns=["match_id", "turn", "team_index", "total_score"]), fmt="png")
    assert _is_png(out)


def test_score_lead_trajectory_png():
    df = pd.DataFrame([
        {"match_id": 1, "turn": 1, "team_index": 0, "total_score": 800_000},
        {"match_id": 1, "turn": 1, "team_index": 1, "total_score": 790_000},
        {"match_id": 1, "turn": 2, "team_index": 0, "total_score": 1_600_000},
        {"match_id": 1, "turn": 2, "team_index": 1, "total_score": 1_620_000},
    ])
    out = plots.score_lead_trajectory(df, fmt="png")
    assert _is_png(out)


# ── comeback_rate ────────────────────────────────────────────────────────────

def test_comeback_rate_empty():
    out = plots.comeback_rate(pd.DataFrame(columns=["match_id", "turn", "team_index", "total_score"]), fmt="png")
    assert _is_png(out)


def test_comeback_rate_png():
    df = pd.DataFrame([
        {"match_id": 1, "turn": 1, "team_index": 0, "total_score": 800_000},
        {"match_id": 1, "turn": 1, "team_index": 1, "total_score": 790_000},
        {"match_id": 1, "turn": 2, "team_index": 0, "total_score": 1_500_000},
        {"match_id": 1, "turn": 2, "team_index": 1, "total_score": 1_620_000},
    ])
    out = plots.comeback_rate(df, fmt="png")
    assert _is_png(out)


# ── action_sankey ────────────────────────────────────────────────────────────

def test_action_sankey_empty():
    out = plots.action_sankey(pd.DataFrame(columns=["match_id", "turn", "team_index", "step", "beatmap_id"]), fmt="png")
    assert _is_png(out)


def test_action_sankey_png():
    df = pd.DataFrame([
        {"match_id": 1, "turn": 1, "team_index": 0, "step": "BAN", "beatmap_id": 100},
        {"match_id": 1, "turn": 2, "team_index": 1, "step": "BAN", "beatmap_id": 101},
        {"match_id": 1, "turn": 3, "team_index": 0, "step": "PICK", "beatmap_id": 102},
    ])
    out = plots.action_sankey(df, fmt="png")
    assert _is_png(out)


# ── player_mod_radar ─────────────────────────────────────────────────────────

def test_player_mod_radar_empty():
    out = plots.player_mod_radar(_scores([]), fmt="png")
    assert _is_png(out)


def test_player_mod_radar_png():
    rows = []
    for uid in range(1, 4):
        for bid in (100, 101, 102):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000 + bid * 100, 1))
    out = plots.player_mod_radar(_scores(rows), fmt="png", mod_group_by_bid={100: "NM", 101: "HD", 102: "HR"})
    assert _is_png(out)


# ── team_rank_distribution ───────────────────────────────────────────────────

def test_team_rank_distribution_empty():
    out = plots.team_rank_distribution(_scores([]), fmt="png")
    assert _is_png(out)


def test_team_rank_distribution_png():
    rows = []
    for uid in range(1, 5):
        for bid in (100, 101):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000, 1))
    df = _scores(rows)
    df["match_id"] = 1
    df["team_index"] = df["user_id"] % 2
    out = plots.team_rank_distribution(df, fmt="png")
    assert _is_png(out)


# ── pp_vs_score_scatter ──────────────────────────────────────────────────────

def test_pp_vs_score_scatter_empty():
    out = plots.pp_vs_score_scatter(_scores([]), fmt="png")
    assert _is_png(out)


def test_pp_vs_score_scatter_png():
    df = _scores([(i, f"u{i}", 100, 700_000 + i * 10_000, 1) for i in range(10)])
    df["pp"] = [100.0 + i * 5 for i in range(10)]
    df["mods"] = '["HD"]'
    out = plots.pp_vs_score_scatter(df, fmt="png")
    assert _is_png(out)


# ── pp_consistency_scatter ───────────────────────────────────────────────────

def test_pp_consistency_scatter_empty():
    out = plots.pp_consistency_scatter(_scores([]), fmt="png")
    assert _is_png(out)


def test_pp_consistency_scatter_png():
    rows = []
    for uid in range(1, 6):
        for bid in (100, 101, 102):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000 + bid * 100, 1))
    out = plots.pp_consistency_scatter(_scores(rows), fmt="png")
    assert _is_png(out)


# ── team_pool_heatmap ────────────────────────────────────────────────────────

def test_team_pool_heatmap_empty():
    out = plots.team_pool_heatmap(pd.DataFrame(columns=["match_id", "team_index", "team_name", "pool_id", "total_score"]), fmt="png")
    assert _is_png(out)


def test_team_pool_heatmap_png():
    df = pd.DataFrame([
        {"match_id": 1, "team_index": 0, "team_name": "A", "pool_id": "P1", "total_score": 800_000},
        {"match_id": 2, "team_index": 0, "team_name": "A", "pool_id": "P2", "total_score": 850_000},
        {"match_id": 1, "team_index": 1, "team_name": "B", "pool_id": "P1", "total_score": 790_000},
    ])
    out = plots.team_pool_heatmap(df, fmt="png")
    assert _is_png(out)


# ── team_strategy_profile ────────────────────────────────────────────────────

def test_team_strategy_profile_empty():
    out = plots.team_strategy_profile(pd.DataFrame(columns=["match_id", "turn", "team_index", "step", "beatmap_id"]), fmt="png")
    assert _is_png(out)


def test_team_strategy_profile_png():
    df = pd.DataFrame([
        {"match_id": 1, "turn": 1, "team_index": 0, "step": "BAN", "beatmap_id": 100},
        {"match_id": 1, "turn": 2, "team_index": 1, "step": "PICK", "beatmap_id": 101},
        {"match_id": 1, "turn": 3, "team_index": 0, "step": "PICK", "beatmap_id": 102},
    ])
    out = plots.team_strategy_profile(df, fmt="png", mod_group_by_bid={100: "NM", 101: "HD", 102: "HR"})
    assert _is_png(out)


# ── team_score_variance ──────────────────────────────────────────────────────

def test_team_score_variance_empty():
    out = plots.team_score_variance(pd.DataFrame(columns=["match_id", "beatmap_id", "team_index", "total_score"]), fmt="png")
    assert _is_png(out)


def test_team_score_variance_png():
    df = pd.DataFrame([
        {"match_id": 1, "beatmap_id": 100, "team_index": 0, "total_score": 800_000},
        {"match_id": 1, "beatmap_id": 100, "team_index": 1, "total_score": 790_000},
        {"match_id": 1, "beatmap_id": 101, "team_index": 0, "total_score": 850_000},
        {"match_id": 1, "beatmap_id": 101, "team_index": 1, "total_score": 820_000},
    ])
    out = plots.team_score_variance(df, fmt="png")
    assert _is_png(out)


# ── score_inflation_curve ────────────────────────────────────────────────────

def test_score_inflation_curve_empty():
    out = plots.score_inflation_curve(pd.DataFrame(columns=["user_id", "username", "beatmap_id", "score", "passed", "round_name"]), fmt="png")
    assert _is_png(out)


def test_score_inflation_curve_png():
    rows = []
    for uid in range(1, 4):
        for bid in (100, 101):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000, 1))
    df = _scores(rows)
    df["round_name"] = "R1"
    out = plots.score_inflation_curve(df, fmt="png")
    assert _is_png(out)


# ── mod_popularity_timeline ──────────────────────────────────────────────────

def test_mod_popularity_timeline_empty():
    out = plots.mod_popularity_timeline(pd.DataFrame(columns=["match_id", "turn", "team_index", "beatmap_id", "round_name"]), fmt="png")
    assert _is_png(out)


def test_mod_popularity_timeline_png():
    df = pd.DataFrame([
        {"match_id": 1, "turn": 1, "team_index": 0, "beatmap_id": 100, "round_name": "R1"},
        {"match_id": 1, "turn": 2, "team_index": 1, "beatmap_id": 101, "round_name": "R1"},
        {"match_id": 2, "turn": 1, "team_index": 0, "beatmap_id": 100, "round_name": "R2"},
    ])
    out = plots.mod_popularity_timeline(df, fmt="png", mod_group_by_bid={100: "NM", 101: "HD"})
    assert _is_png(out)


# ── fm_mod_combo_stack ───────────────────────────────────────────────────────

def test_fm_mod_combo_stack_empty():
    out = plots.fm_mod_combo_stack(pd.DataFrame(columns=["user_id", "username", "beatmap_id", "score", "passed", "mods"]), fmt="png")
    assert _is_png(out)


def test_fm_mod_combo_stack_png():
    df = pd.DataFrame([
        {"user_id": 1, "username": "a", "beatmap_id": 100, "score": 800_000, "passed": 1, "mods": '["HD"]'},
        {"user_id": 2, "username": "b", "beatmap_id": 100, "score": 750_000, "passed": 1, "mods": '["HR"]'},
        {"user_id": 3, "username": "c", "beatmap_id": 100, "score": 820_000, "passed": 1, "mods": '["HD","HR"]'},
    ])
    out = plots.fm_mod_combo_stack(df, fmt="png", mod_group_by_bid={100: "FM"})
    assert _is_png(out)


# ── upset_rate_by_round ──────────────────────────────────────────────────────

def test_upset_rate_by_round_empty():
    out = plots.upset_rate_by_round(pd.DataFrame(columns=["round_name", "upset"]), fmt="png")
    assert _is_png(out)


def test_upset_rate_by_round_png():
    df = pd.DataFrame([
        {"round_name": "R1", "upset": 1},
        {"round_name": "R1", "upset": 0},
        {"round_name": "R1", "upset": 1},
        {"round_name": "R2", "upset": 0},
        {"round_name": "R2", "upset": 0},
    ])
    out = plots.upset_rate_by_round(df, fmt="png")
    assert _is_png(out)
