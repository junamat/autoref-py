"""Seed matches.db with one of the bundled tournament fixtures.

Each dataset becomes a set of synthetic matches in `matches`, plus
`match_actions` for picks/bans (no protects: the 2v2 dataset's protect
mechanic was DM-based and doesn't fit our model) and `game_scores` for
the cross-match stats. Pool entries are also written to PoolStore so
the /stats page surfaces tournament codes (NM1, HD2…) instead of raw
beatmap IDs.

Usage:
    python scripts/seed_db.py --dataset 4wc      # default
    python scripts/seed_db.py --dataset 2v2
    python scripts/seed_db.py --dataset 4wc --db matches.db
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# 4WC qualifiers — one CSV with score data + pick codes already in-row
# ─────────────────────────────────────────────────────────────────────────────

def _seed_4wc_pool(df: pd.DataFrame) -> None:
    """Mirror the 4WC fixture's pick codes into PoolStore."""
    from autoref.core.pool_store import PoolStore

    by_bid: dict[int, dict] = {}
    for _, row in df.iterrows():
        bid = int(row["beatmap_id"])
        pick = (row.get("pick") or "").strip() if pd.notna(row.get("pick")) else ""
        mods = (row.get("mods") or "").strip() if pd.notna(row.get("mods")) else ""
        if not pick:
            continue
        entry = by_bid.setdefault(bid, {"code": pick, "mods_counts": {}})
        if mods:
            entry["mods_counts"][mods] = entry["mods_counts"].get(mods, 0) + 1

    groups: dict[str, list[dict]] = {}
    for bid, info in by_bid.items():
        prefix = re.match(r"[A-Za-z]+", info["code"])
        group_name = prefix.group(0).upper() if prefix else "MISC"
        dominant_mod = (max(info["mods_counts"], key=info["mods_counts"].get)
                        if info["mods_counts"] else "")
        groups.setdefault(group_name, []).append({
            "type": "map",
            "bid": str(bid),
            "code": info["code"],
            "mods": dominant_mod,
        })

    tree = []
    for group_name, maps in groups.items():
        maps.sort(key=lambda m: int(re.sub(r"[^0-9]", "", m["code"]) or 0))
        group_mods_count: dict[str, int] = {}
        for m in maps:
            if m["mods"]:
                group_mods_count[m["mods"]] = group_mods_count.get(m["mods"], 0) + 1
        group_mods = (max(group_mods_count, key=group_mods_count.get)
                      if group_mods_count else "")
        tree.append({
            "type": "pool",
            "name": group_name,
            "mods": group_mods,
            "children": maps,
        })

    PoolStore().save({
        "id": "seed_4wc_qualifiers",
        "name": "Seed: 4WC Qualifiers",
        "tree": tree,
    })


def seed_4wc(db_path: str) -> None:
    csv_path = FIXTURES / "qualifiers_4wc_scores.csv"
    df = pd.read_csv(csv_path)

    _seed_4wc_pool(df)

    conn = sqlite3.connect(db_path)

    from autoref.core.storage import MatchDatabase
    MatchDatabase(db_path).close()

    for mp_id, group in df.groupby("match_id"):
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE winner_team = ?", (f"seed:{mp_id}",)
        ).fetchone()
        if existing:
            print(f"  skip mp/{mp_id} (already seeded)")
            continue

        cur = conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, "
            "bans_per_team, protects_per_team, winner_team, pool_id, round_name) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (1, "osu", "SCORE_V2", 1, "0", "0", f"seed:{mp_id}",
             "seed_4wc_qualifiers", "Qualifiers"),
        )
        match_id = cur.lastrowid

        conn.execute(
            "INSERT INTO match_teams VALUES (?,?,?)", (match_id, 0, "qualifiers")
        )

        for turn, (beatmap_id, _) in enumerate(group.groupby("beatmap_id", sort=False)):
            conn.execute(
                "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (match_id, turn, 0, "PICK", int(beatmap_id)),
            )

        for turn, (beatmap_id, map_group) in enumerate(group.groupby("beatmap_id", sort=False)):
            for _, row in map_group.iterrows():
                mods = [row["mods"]] if pd.notna(row.get("mods")) and row["mods"] not in ("NM", "") else []
                conn.execute(
                    "INSERT INTO game_scores "
                    "(match_id, turn, beatmap_id, user_id, username, team_index, "
                    " score, accuracy, max_combo, mods, passed, perfect, rank) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        match_id, turn, int(row["beatmap_id"]),
                        int(row["user_id"]), str(row["username"]), 0,
                        int(row["score"]), float(row["accuracy"]), 0,
                        json.dumps(mods), int(row["passed"]), 0, None,
                    ),
                )

        conn.commit()
        print(f"  seeded mp/{mp_id} → match_id={match_id} ({len(group)} scores)")

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2v2 Round of 16 — multi-CSV: scores + mappool + players + picks/bans
# ─────────────────────────────────────────────────────────────────────────────

def _seed_2v2_pool(mappool: pd.DataFrame) -> None:
    from autoref.core.pool_store import PoolStore

    groups: dict[str, list[dict]] = {}
    for _, row in mappool.iterrows():
        pick = str(row["pick"]).strip()
        bid  = str(int(row["beatmap_id"]))
        if not pick:
            continue
        prefix = re.match(r"[A-Za-z]+", pick)
        group_name = prefix.group(0).upper() if prefix else "MISC"
        groups.setdefault(group_name, []).append({
            "type": "map",
            "bid": bid,
            "code": pick,
            "mods": "",  # mods inferred from group prefix; pool builder fills in
        })

    # mod inferred from group name (TB is freemod by tournament convention)
    group_mods = {"NM": "", "HD": "HD", "HR": "HR", "DT": "DT", "EZ": "EZ",
                  "FM": "Freemod", "DR": "HRDT", "TB": "Freemod"}
    tree = []
    for group_name, maps in groups.items():
        maps.sort(key=lambda m: int(re.sub(r"[^0-9]", "", m["code"]) or 0))
        gm = group_mods.get(group_name, "")
        for m in maps:
            m["mods"] = gm
        tree.append({
            "type": "pool",
            "name": group_name,
            "mods": gm,
            "children": maps,
        })

    PoolStore().save({
        "id": "seed_2v2_round_of_16",
        "name": "Seed: 2v2 Round of 16",
        "tree": tree,
    })


def seed_2v2(db_path: str) -> None:
    scores  = pd.read_csv(FIXTURES / "2v2_round_of_16_scores.csv")
    mappool = pd.read_csv(FIXTURES / "2v2_round_of_16_mappool.csv")
    pb      = pd.read_csv(FIXTURES / "2v2_picks_bans.csv")

    _seed_2v2_pool(mappool)

    conn = sqlite3.connect(db_path)

    from autoref.core.storage import MatchDatabase
    MatchDatabase(db_path).close()

    pick_to_bid = {row["pick"]: int(row["beatmap_id"]) for _, row in mappool.iterrows()}
    pb_by_match = {int(row["match_id"]): row for _, row in pb.iterrows()}

    # Only F counts as a fail in osu!; D-S(S) all pass. " S " (whitespace-padded
    # SS in the source) is trimmed before comparison.
    def _is_pass(rank: str) -> int:
        r = (rank or "").strip().upper()
        return 0 if r == "F" else 1

    for mp_id, group in scores.groupby("match_id"):
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE winner_team = ?", (f"seed2v2:{mp_id}",)
        ).fetchone()
        if existing:
            print(f"  skip mp/{mp_id} (already seeded)")
            continue

        # team_index: first team encountered in this match → 0, second → 1
        teams_in_order: list[str] = []
        for _, row in group.iterrows():
            t = row["team"]
            if t not in teams_in_order:
                teams_in_order.append(t)
        team_idx = {t: i for i, t in enumerate(teams_in_order)}

        cur = conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, "
            "bans_per_team, protects_per_team, winner_team, pool_id, round_name) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (1, "osu", "SCORE_V2", 9, "2", "0", f"seed2v2:{mp_id}",
             "seed_2v2_round_of_16", "Round of 16"),
        )
        match_id = cur.lastrowid

        for t, idx in team_idx.items():
            conn.execute("INSERT INTO match_teams VALUES (?,?,?)", (match_id, idx, t))

        # match_actions from the picks/bans sheet (per-team alternation unknown
        # from the source data, so all actions are credited to team 0 — totals
        # are correct; per-team breakdown is not).
        # Protects: the source tournament used a DM-secret mechanic that doesn't
        # match how we model protects; we sample only the first listed protect
        # per match (8 of 16 source rows) so the heat plot has signal without
        # overstating coverage.
        pb_row = pb_by_match.get(int(mp_id))
        turn = 0
        if pb_row is not None:
            picks_str    = str(pb_row.get("picks",    "")) if pd.notna(pb_row.get("picks"))    else ""
            bans_str     = str(pb_row.get("bans",     "")) if pd.notna(pb_row.get("bans"))     else ""
            protects_str = str(pb_row.get("protects", "")) if pd.notna(pb_row.get("protects")) else ""

            protect_codes = [c.strip() for c in protects_str.split(",") if c.strip()][:1]
            for code in protect_codes:
                bid = pick_to_bid.get(code)
                if bid is None: continue
                conn.execute(
                    "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                    "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (match_id, turn, 0, "PROTECT", bid),
                )
                turn += 1
            for code in [c.strip() for c in bans_str.split(",") if c.strip()]:
                bid = pick_to_bid.get(code)
                if bid is None: continue
                conn.execute(
                    "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                    "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (match_id, turn, 0, "BAN", bid),
                )
                turn += 1
            for code in [c.strip() for c in picks_str.split(",") if c.strip()]:
                bid = pick_to_bid.get(code)
                if bid is None: continue
                conn.execute(
                    "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                    "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (match_id, turn, 0, "PICK", bid),
                )
                turn += 1

        # game_scores: one turn per (match, beatmap_id) ordered by score_id
        # (score_id starts with the lobby-internal game id, monotonically rising).
        ordered = group.copy()
        ordered["_game"] = ordered["score_id"].str.split("-").str[0].astype(int)
        ordered = ordered.sort_values("_game")

        bid_to_turn: dict[int, int] = {}
        for _, row in ordered.iterrows():
            pick = row["pick"]
            bid  = pick_to_bid.get(pick)
            if bid is None:
                continue
            if bid not in bid_to_turn:
                bid_to_turn[bid] = len(bid_to_turn)
            t_idx = team_idx.get(row["team"], 0)
            mods_field = (row.get("mods") or "").strip().upper()
            mods_list = [mods_field] if mods_field and mods_field != "NM" else []
            uid = int(row["user_id"]) if pd.notna(row["user_id"]) and str(row["user_id"]).strip() else 0
            conn.execute(
                "INSERT INTO game_scores "
                "(match_id, turn, beatmap_id, user_id, username, team_index, "
                " score, accuracy, max_combo, mods, passed, perfect, rank) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    match_id, bid_to_turn[bid], bid,
                    uid, str(row["player"]), t_idx,
                    int(row["score"]), float(row["accuracy"]), 0,
                    json.dumps(mods_list), _is_pass(str(row["rank"])), 0,
                    str(row["rank"]).strip(),
                ),
            )

        conn.commit()
        print(f"  seeded mp/{mp_id} → match_id={match_id} "
              f"({len(group)} scores, teams={teams_in_order})")

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# DI Round of 32 — same shape as 2v2, but picks-only (no bans/protects in source)
# ─────────────────────────────────────────────────────────────────────────────

def _seed_di_pool(mappool: pd.DataFrame) -> None:
    from autoref.core.pool_store import PoolStore

    groups: dict[str, list[dict]] = {}
    for _, row in mappool.iterrows():
        pick = str(row["pick"]).strip()
        bid  = str(int(row["beatmap_id"]))
        if not pick:
            continue
        prefix = re.match(r"[A-Za-z]+", pick)
        group_name = prefix.group(0).upper() if prefix else "MISC"
        groups.setdefault(group_name, []).append({
            "type": "map", "bid": bid, "code": pick, "mods": "",
        })

    group_mods = {"NM": "", "HD": "HD", "HR": "HR", "DT": "DT", "EZ": "EZ",
                  "FM": "Freemod", "DR": "HRDT", "TB": "Freemod"}
    tree = []
    for group_name, maps in groups.items():
        maps.sort(key=lambda m: int(re.sub(r"[^0-9]", "", m["code"]) or 0))
        gm = group_mods.get(group_name, "")
        for m in maps:
            m["mods"] = gm
        tree.append({"type": "pool", "name": group_name, "mods": gm, "children": maps})

    PoolStore().save({
        "id": "seed_di_round_of_32",
        "name": "Seed: DI Round of 32",
        "tree": tree,
    })


def seed_di(db_path: str) -> None:
    scores  = pd.read_csv(FIXTURES / "di_round_of_32_scores.csv")
    mappool = pd.read_csv(FIXTURES / "di_round_of_32_mappool.csv")
    pb      = pd.read_csv(FIXTURES / "di_picks_bans.csv")

    _seed_di_pool(mappool)

    conn = sqlite3.connect(db_path)
    from autoref.core.storage import MatchDatabase
    MatchDatabase(db_path).close()

    pick_to_bid = {row["pick"]: int(row["beatmap_id"]) for _, row in mappool.iterrows()}
    pb_by_match = {int(row["match_id"]): row for _, row in pb.iterrows()}

    def _is_pass(rank: str) -> int:
        return 0 if (rank or "").strip().upper() == "F" else 1

    # mods column is e.g. "NFHD", "NFDT" — strip NF (enforced) before storing.
    def _split_mods(field: str) -> list[str]:
        s = (field or "").strip().upper().replace("NF", "")
        if not s or s == "NM":
            return []
        out, i = [], 0
        while i < len(s):
            out.append(s[i:i+2])
            i += 2
        return out

    for mp_id, group in scores.groupby("match_id"):
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE winner_team = ?", (f"seeddi:{mp_id}",)
        ).fetchone()
        if existing:
            print(f"  skip mp/{mp_id} (already seeded)")
            continue

        teams_in_order: list[str] = []
        for _, row in group.iterrows():
            t = row["team"]
            if pd.notna(t) and t not in teams_in_order:
                teams_in_order.append(t)
        team_idx = {t: i for i, t in enumerate(teams_in_order)}

        cur = conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, "
            "bans_per_team, protects_per_team, winner_team, pool_id, round_name) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (1, "osu", "SCORE_V2", 11, "0", "0", f"seeddi:{mp_id}",
             "seed_di_round_of_32", "Round of 32"),
        )
        match_id = cur.lastrowid

        for t, idx in team_idx.items():
            conn.execute("INSERT INTO match_teams VALUES (?,?,?)", (match_id, idx, t))

        pb_row = pb_by_match.get(int(mp_id))
        turn = 0
        if pb_row is not None:
            picks_str = str(pb_row.get("picks", "")) if pd.notna(pb_row.get("picks")) else ""
            for code in [c.strip() for c in picks_str.split(",") if c.strip()]:
                bid = pick_to_bid.get(code)
                if bid is None: continue
                conn.execute(
                    "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                    "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (match_id, turn, 0, "PICK", bid),
                )
                turn += 1

        # Source has no game-id ordering; rely on row order in the CSV.
        bid_to_turn: dict[int, int] = {}
        for _, row in group.iterrows():
            pick = row["pick"]
            bid = pick_to_bid.get(pick)
            if bid is None:
                continue
            if bid not in bid_to_turn:
                bid_to_turn[bid] = len(bid_to_turn)
            t_idx = team_idx.get(row["team"], 0)
            uid = int(row["user_id"]) if pd.notna(row["user_id"]) and str(row["user_id"]).strip() else 0
            conn.execute(
                "INSERT INTO game_scores "
                "(match_id, turn, beatmap_id, user_id, username, team_index, "
                " score, accuracy, max_combo, mods, passed, perfect, rank) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    match_id, bid_to_turn[bid], bid,
                    uid, str(row["player"]), t_idx,
                    int(row["score"]), float(row["accuracy"]), 0,
                    json.dumps(_split_mods(str(row.get("mods") or ""))),
                    _is_pass(str(row["rank"])), 0, str(row["rank"]).strip(),
                ),
            )

        conn.commit()
        print(f"  seeded mp/{mp_id} → match_id={match_id} "
              f"({len(group)} scores, teams={teams_in_order})")

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# DI Qualifiers — same shape as 4WC qualifiers (one CSV, picks in-row)
# ─────────────────────────────────────────────────────────────────────────────

def seed_di_quals(db_path: str) -> None:
    csv_path = FIXTURES / "di_qualifiers_scores.csv"
    df = pd.read_csv(csv_path)

    # user_id → team mapping from the players fixture
    players = pd.read_csv(FIXTURES / "di_players.csv")
    uid_to_team: dict[int, str] = {
        int(r["user_id"]): str(r["team"]) for _, r in players.iterrows()
    }

    # Reuse the 4WC pool builder; it groups by pick prefix and writes to PoolStore.
    # Override the saved pool's id/name so it doesn't collide with seed_4wc_qualifiers.
    _seed_4wc_pool(df)
    from autoref.core.pool_store import PoolStore
    store = PoolStore()
    saved = store.get("seed_4wc_qualifiers")
    if saved is not None:
        store.delete("seed_4wc_qualifiers")
        saved["id"] = "seed_di_qualifiers"
        saved["name"] = "Seed: DI Qualifiers"
        store.save(saved)

    conn = sqlite3.connect(db_path)
    from autoref.core.storage import MatchDatabase
    MatchDatabase(db_path).close()

    for mp_id, group in df.groupby("match_id"):
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE winner_team = ?", (f"seeddiq:{mp_id}",)
        ).fetchone()
        if existing:
            print(f"  skip mp/{mp_id} (already seeded)")
            continue

        cur = conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, "
            "bans_per_team, protects_per_team, winner_team, pool_id, round_name) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (1, "osu", "SCORE_V2", 1, "0", "0", f"seeddiq:{mp_id}",
             "seed_di_qualifiers", "Qualifiers"),
        )
        match_id = cur.lastrowid

        # Distinct teams in this lobby (in order of first appearance), skipping
        # players we don't have a roster row for (they get team_index 0 with a
        # placeholder team named after the lobby).
        teams_in_order: list[str] = []
        for _, row in group.iterrows():
            t = uid_to_team.get(int(row["user_id"]))
            if t and t not in teams_in_order:
                teams_in_order.append(t)
        if not teams_in_order:
            teams_in_order = [f"qualifiers mp/{mp_id}"]
        team_idx = {t: i for i, t in enumerate(teams_in_order)}
        for t, idx in team_idx.items():
            conn.execute("INSERT INTO match_teams VALUES (?,?,?)", (match_id, idx, t))

        for turn, (beatmap_id, _) in enumerate(group.groupby("beatmap_id", sort=False)):
            conn.execute(
                "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (match_id, turn, 0, "PICK", int(beatmap_id)),
            )

        for turn, (beatmap_id, map_group) in enumerate(group.groupby("beatmap_id", sort=False)):
            for _, row in map_group.iterrows():
                mods_field = (row.get("mods") or "").strip().upper()
                mods = [mods_field] if mods_field and mods_field != "NM" else []
                team_name = uid_to_team.get(int(row["user_id"]), teams_in_order[0])
                t_idx = team_idx.get(team_name, 0)
                conn.execute(
                    "INSERT INTO game_scores "
                    "(match_id, turn, beatmap_id, user_id, username, team_index, "
                    " score, accuracy, max_combo, mods, passed, perfect, rank) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        match_id, turn, int(row["beatmap_id"]),
                        int(row["user_id"]), str(row["username"]), t_idx,
                        int(row["score"]), float(row["accuracy"]), 0,
                        json.dumps(mods), int(row["passed"]), 0, None,
                    ),
                )

        conn.commit()
        print(f"  seeded mp/{mp_id} → match_id={match_id} "
              f"({len(group)} scores, teams={teams_in_order})")

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────

DATASETS = {
    "4wc":     (seed_4wc,      "4WC 2025 Open Qualifiers (1v1 score-only)"),
    "2v2":     (seed_2v2,      "2v2 Round of 16 (full picks/bans + scores)"),
    "di":      (seed_di,       "DI Round of 32 (2v2, picks-only)"),
    "di_quals":(seed_di_quals, "DI Qualifiers (2v2 quals, score-only)"),
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASETS.keys(), default="4wc")
    parser.add_argument("--db", default="matches.db")
    args = parser.parse_args()
    fn, desc = DATASETS[args.dataset]
    print(f"Seeding {args.db} with {args.dataset!r} → {desc}")
    fn(args.db)
    print("Done. Open http://localhost:8080/stats to view.")
