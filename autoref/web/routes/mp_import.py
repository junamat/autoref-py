"""MP link import routes."""
import logging
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    from ...client import make_client
    from ...core.mp_importer import fetch_mp_match, save_imported_match_with_pp
    from ...core.mp_link import parse_mp_link
    from .._auth_dep import require_not_player

    @app.post("/api/mp/preview")
    async def preview_mp_link(request: Request, user=Depends(require_not_player)):
        """Fetch match data from MP link and return preview with inferred teams."""
        try:
            body = await request.json()
            url = body.get("url", "")

            mp_link = parse_mp_link(url)
            if mp_link is None:
                return JSONResponse({"error": "invalid_mp_link"}, status_code=400)

            async with make_client() as client:
                imported = await fetch_mp_match(client, mp_link)

            if not imported.games:
                return JSONResponse({"error": "no_games_found"}, status_code=400)

            sorted_users = sorted(imported.users.items())
            players = [
                {"user_id": uid, "username": uname, "team_index": i, "enabled": True}
                for i, (uid, uname) in enumerate(sorted_users)
            ]

            games = [
                {
                    "beatmap_id": g.beatmap_id,
                    "num_scores": len(g.scores),
                }
                for g in imported.games
            ]

            return JSONResponse({
                "match_id": imported.match_id,
                "name": imported.name,
                "match_type": imported.match_type,
                "num_games": len(imported.games),
                "players": players,
                "games": games,
            })

        except Exception:
            logger.exception("failed to preview mp link")
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.post("/api/mp/import")
    async def import_mp_link(request: Request, user=Depends(require_not_player)):
        """Import match with confirmed team assignments."""
        try:
            body = await request.json()
            url = body.get("url", "")
            players = body.get("players", [])
            pool_id = body.get("pool_id")
            round_name = body.get("round_name")

            mp_link = parse_mp_link(url)
            if mp_link is None:
                return JSONResponse({"error": "invalid_mp_link"}, status_code=400)

            async with make_client() as client:
                imported = await fetch_mp_match(client, mp_link)

            if not imported.games:
                return JSONResponse({"error": "no_games_found"}, status_code=400)

            enabled_players = {p["user_id"]: p for p in players if p.get("enabled", True)}

            filtered_games = []
            for game in imported.games:
                filtered_scores = [
                    s for s in game.scores
                    if s["user_id"] in enabled_players
                ]
                if filtered_scores:
                    from ...core.mp_importer import ImportedGame
                    filtered_games.append(ImportedGame(
                        beatmap_id=game.beatmap_id,
                        scores=filtered_scores,
                        start_time=game.start_time,
                        end_time=game.end_time,
                    ))

            if not filtered_games:
                return JSONResponse({"error": "no_valid_scores"}, status_code=400)

            imported.games = filtered_games
            imported.users = {
                uid: uname for uid, uname in imported.users.items()
                if uid in enabled_players
            }

            for uid, new_name in imported.users.items():
                existing = server.db._conn.execute(
                    "SELECT DISTINCT username FROM game_scores WHERE user_id = ? AND username != ? LIMIT 1",
                    (uid, new_name),
                ).fetchone()
                if existing:
                    old_name = existing[0]
                    server.db._conn.execute(
                        "UPDATE game_scores SET username = ? WHERE user_id = ?",
                        (new_name, uid),
                    )
                    server.db._conn.execute(
                        "UPDATE match_teams SET team_name = ? WHERE team_name = ?",
                        (new_name, old_name),
                    )

            mid = await save_imported_match_with_pp(
                server.db,
                imported,
                pool_id=pool_id,
                round_name=round_name,
            )

            return JSONResponse({
                "match_id": mid,
                "imported": True,
                "num_games": len(filtered_games),
                "num_players": len(enabled_players),
            })

        except Exception:
            logger.exception("failed to import mp link")
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.delete("/api/mp/imported/{match_id}")
    async def delete_imported_match(match_id: int, user=Depends(require_not_player)):
        """Delete an imported match and all associated data from the database."""
        deleted = server.db.matches.delete_match(match_id)
        if not deleted:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({"ok": True, "deleted": match_id})

    @app.get("/api/mp/refresh/{match_id}")
    async def refresh_match(match_id: int, user=Depends(require_not_player)):
        """Fetch fresh data from osu! API and compare with existing scores."""
        try:
            row = server.db._conn.execute(
                "SELECT osu_match_id FROM matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()

            if not row or not row[0]:
                return JSONResponse({"error": "no_osu_match_id"}, status_code=400)

            osu_match_id = row[0]

            from ...core.mp_link import MpLink
            mp_link = MpLink(osu_match_id)

            async with make_client() as client:
                imported = await fetch_mp_match(client, mp_link)

            if not imported.games:
                return JSONResponse({"error": "no_games_found"}, status_code=400)

            existing = server.db.scores.by_match(match_id)
            existing_keys = set()
            existing_usernames = {}
            for _, r in existing.iterrows():
                existing_keys.add((int(r["turn"]), int(r["beatmap_id"]), int(r["user_id"])))
                uid = int(r["user_id"])
                if uid not in existing_usernames and r.get("username"):
                    existing_usernames[uid] = r["username"]

            name_changes = []
            for uid, old_name in existing_usernames.items():
                new_name = imported.users.get(uid)
                if new_name and new_name != old_name:
                    name_changes.append({"user_id": uid, "old_name": old_name, "new_name": new_name})

            new_games = []
            for turn_offset, game in enumerate(imported.games, start=1):
                new_scores = []
                for s in game.scores:
                    key = (turn_offset, game.beatmap_id, s["user_id"])
                    if key not in existing_keys:
                        new_scores.append({
                            "user_id": s["user_id"],
                            "username": s.get("username"),
                            "score": s["score"],
                            "accuracy": s["accuracy"],
                            "max_combo": s["max_combo"],
                            "passed": s["passed"],
                            "mods": s["mods"],
                            "rank": s.get("rank"),
                            "team_index": s.get("team_index"),
                        })
                if new_scores:
                    new_games.append({
                        "turn": turn_offset,
                        "beatmap_id": game.beatmap_id,
                        "scores": new_scores,
                    })

            sorted_users = sorted(imported.users.items())
            players = [
                {"user_id": uid, "username": uname, "team_index": i}
                for i, (uid, uname) in enumerate(sorted_users)
            ]

            return JSONResponse({
                "match_id": match_id,
                "osu_match_id": osu_match_id,
                "name": imported.name,
                "total_games": len(imported.games),
                "new_games": new_games,
                "name_changes": name_changes,
                "players": players,
            })

        except Exception:
            logger.exception("failed to refresh match %d", match_id)
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.post("/api/mp/refresh/{match_id}/apply")
    async def apply_refresh(match_id: int, request: Request, user=Depends(require_not_player)):
        """Apply new scores and name changes from a refresh operation."""
        try:
            body = await request.json()
            new_games = body.get("new_games", [])
            name_changes = body.get("name_changes", [])

            if not new_games and not name_changes:
                return JSONResponse({"error": "no_changes"}, status_code=400)

            row = server.db._conn.execute(
                "SELECT pool_id, round_name FROM matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()

            if not row:
                return JSONResponse({"error": "not_found"}, status_code=404)

            scores_iter = []
            for game in new_games:
                turn = game["turn"]
                beatmap_id = game["beatmap_id"]
                scores = game["scores"]
                scores_iter.append((turn, beatmap_id, scores))

            if scores_iter:
                server.db.scores.insert_scores(match_id, scores_iter, {})

            for change in name_changes:
                user_id = change["user_id"]
                new_name = change["new_name"]
                server.db._conn.execute(
                    "UPDATE game_scores SET username = ? WHERE user_id = ?",
                    (new_name, user_id),
                )
                server.db._conn.execute(
                    "UPDATE match_teams SET team_name = ? WHERE team_name = ?",
                    (new_name, change["old_name"]),
                )

            server.db._conn.commit()

            total_new = sum(len(g["scores"]) for g in new_games)

            return JSONResponse({
                "ok": True,
                "match_id": match_id,
                "new_games": len(new_games),
                "new_scores": total_new,
                "name_changes": len(name_changes),
            })

        except Exception:
            logger.exception("failed to apply refresh for match %d", match_id)
            return JSONResponse({"error": "internal_error"}, status_code=500)
