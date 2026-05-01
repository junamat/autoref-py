"""Web interface: per-match WebInterface + shared WebServer registry."""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


from ..core.pool_store import PoolStore
from ..core.beatmap_cache import get_beatmap_cache
_POOL_STORE = PoolStore()


def _flatten_pool_tree(nodes: list, parent_mods: str = "") -> list:
    from ..factory import flatten_pool_tree as _ft
    return _ft(nodes, parent_mods)


def _build_map_code_lookup() -> dict[int, str]:
    """Walk every saved pool, return {beatmap_id: code} (e.g. {3814680: "NM1"}).

    On collisions across pools, the last one wins. Acceptable for one-tournament
    use; revisit if multi-tournament aggregation becomes a real use case.
    """
    lookup: dict[int, str] = {}

    def _walk(nodes):
        for n in nodes:
            if n.get("type") == "map":
                bid = n.get("bid")
                code = n.get("code")
                if bid and code:
                    try:
                        lookup[int(bid)] = str(code)
                    except (TypeError, ValueError):
                        pass
            elif n.get("children"):
                _walk(n["children"])

    for pool in _POOL_STORE.list():
        _walk(pool.get("tree", []))
    return lookup


def _build_map_order_lookup() -> dict[int, int]:
    """Walk every saved pool in tree order, return {beatmap_id: position}.

    Position is the 0-based index of the map in the flattened pool tree
    (NM1=0, NM2=1, ..., HD1=N, ...). Used to sort standings/results maps
    in pool order rather than by pick count.
    """
    order: dict[int, int] = {}
    counter = 0

    def _walk(nodes):
        nonlocal counter
        for n in nodes:
            if n.get("type") == "map":
                bid = n.get("bid")
                if bid:
                    try:
                        bid_int = int(bid)
                        if bid_int not in order:
                            order[bid_int] = counter
                            counter += 1
                    except (TypeError, ValueError):
                        pass
            elif n.get("children"):
                _walk(n["children"])

    for pool in _POOL_STORE.list():
        _walk(pool.get("tree", []))
    return order


class WebInterface:
    """Attaches to one AutoRef instance; registered into a WebServer."""

    def __init__(self, match_id: str | None = None):
        self.match_id: str = match_id or str(uuid.uuid4())[:8]
        self._clients: set = set()
        self._lobby = None
        self._last_state: dict | None = None
        self._server: "WebServer | None" = None

    def attach(self, lobby) -> None:
        self._lobby = lobby
        lobby.add_message_hook(self._on_message)
        lobby.register_reply_sink("web", self._reply)

    def attach_autoref(self, ar) -> None:
        ar.add_state_hook(self._on_state)

    # ---------------------------------------------------------------- hooks

    async def _reply(self, text: str) -> None:
        """Reply sink: send text only to web clients (not to Bancho)."""
        await self._broadcast(json.dumps({"type": "reply", "text": text}))

    async def _on_message(self, username: str, message: str, outgoing: bool) -> None:
        await self._broadcast(json.dumps({
            "type": "chat",
            "username": username,
            "message": message,
            "outgoing": outgoing,
        }))

    async def _on_state(self, state: dict) -> None:
        self._last_state = state
        if self._server:
            self._server._notify_landing()
        await self._broadcast(json.dumps({"type": "state", **state}))

    async def _broadcast(self, payload: str) -> None:
        dead = set()
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead.add(client)
        self._clients -= dead

    def summary(self) -> dict:
        """Compact summary for /api/matches."""
        s = self._last_state or {}
        return {
            "id":          self.match_id,
            "active":      True,
            "qualifier":   s.get("qualifier", False),
            "mode":        s.get("mode", "off"),
            "team_names":  s.get("team_names", []),
            "best_of":     s.get("best_of"),
            "ref_name":    s.get("ref_name"),
            "maps_played": s.get("maps_played"),
            "total_maps":  s.get("total_maps"),
            "phase":       s.get("phase"),
        }


class WebServer:
    """Shared FastAPI server. Register WebInterface instances before calling start()."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 static_dir: str | Path | None = None,
                 bancho_username: str | None = None,
                 bancho_password: str | None = None,
                 db_path: str | Path | None = None):
        from ..core.storage import MatchDatabase
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._matches: dict[str, WebInterface] = {}
        self._pending: dict[str, dict] = {}   # match_id -> raw payload, not yet started
        self._landing_clients: set = set()
        self._bancho_username = bancho_username or os.getenv("BANCHO_USERNAME", "")
        self._bancho_password = bancho_password or os.getenv("BANCHO_PASSWORD", "")
        self._tasks: dict[str, asyncio.Task] = {}
        # Single shared sqlite file for cross-match stats. Override path with $AUTOREF_DB.
        self.db = MatchDatabase(db_path or os.getenv("AUTOREF_DB", "matches.db"))

    def register(self, iface: WebInterface) -> WebInterface:
        """Add a WebInterface to the registry. Returns the interface for chaining."""
        iface._server = self
        self._matches[iface.match_id] = iface
        return iface

    def unregister(self, iface: WebInterface) -> None:
        self._matches.pop(iface.match_id, None)
        self._tasks.pop(iface.match_id, None)
        asyncio.ensure_future(iface._broadcast(json.dumps({"type": "done"})))
        self._notify_landing()

    def _notify_landing(self) -> None:
        """Push updated match list to all landing-page clients."""
        all_matches = (
            [self._pending_summary(mid, p) for mid, p in self._pending.items()] +
            [m.summary() for m in self._matches.values()]
        )
        payload = json.dumps({"type": "matches", "matches": all_matches})
        dead = set()
        for client in self._landing_clients:
            try:
                asyncio.ensure_future(client.send_text(payload))
            except Exception:
                dead.add(client)
        self._landing_clients -= dead

    def _pending_summary(self, match_id: str, payload: dict) -> dict:
        teams = payload.get("teams", [])
        return {
            "id":         match_id,
            "status":     "pending",
            "qualifier":  payload.get("type") == "qualifiers",
            "mode":       payload.get("mode", "off"),
            "team_names": [t["name"] for t in teams],
            "best_of":    payload.get("best_of"),
        }

    async def _create_match(self, payload: dict, match_id: str | None = None) -> WebInterface:
        """Spin up an AutoRef from a web payload and register it."""
        from ..factory import build_autoref

        def _pool_loader(pool_id):
            return _POOL_STORE.get(pool_id)

        ar, client = await build_autoref(
            payload,
            bancho_username=self._bancho_username,
            bancho_password=self._bancho_password,
            pool_loader=_pool_loader,
            db=self.db,
        )

        iface = WebInterface(match_id=match_id)
        self.register(iface)
        iface.attach(ar.lobby)
        iface.attach_autoref(ar)

        async def _run():
            try:
                await client.connect()
                await ar.run()
            except Exception:
                logger.exception("match %s crashed", iface.match_id)
            finally:
                await client.disconnect()
                self.unregister(iface)

        self._tasks[iface.match_id] = asyncio.create_task(_run())
        return iface

    async def start(self) -> None:
        from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        app = FastAPI()
        server = self

        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(self.static_dir / "index.html")

        @app.get("/pool-builder")
        async def pool_builder():
            return FileResponse(self.static_dir / "pool_builder.html")

        @app.get("/stats")
        async def stats_page():
            return FileResponse(self.static_dir / "stats.html")

        @app.get("/api/stats")
        async def api_stats(method: str = "zscore", count_failed: bool = True, aggregate: str = "sum",
                            pool_id: str | None = None, round_name: str | None = None):
            from ..core.stats import include_all, exclude_failed, METHODS, PP_METHODS, leaderboard_async
            if method not in METHODS:
                return JSONResponse({"error": f"unknown method: {method}"}, status_code=400)
            if aggregate not in ("sum", "mean"):
                return JSONResponse({"error": f"aggregate must be 'sum' or 'mean'"}, status_code=400)
            predicate = include_all if count_failed else exclude_failed
            if method in PP_METHODS:
                all_scores_for_lb = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
                leaderboard = await leaderboard_async(all_scores_for_lb, method=method,
                                                      include=predicate, aggregate=aggregate,
                                                      db=server.db)
            else:
                leaderboard = server.db.get_leaderboard(method=method, include=predicate, aggregate=aggregate,
                                                        pool_id=pool_id, round_name=round_name)
            map_stats   = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
            map_breakdown = server.db.get_map_action_breakdown(pool_id=pool_id, round_name=round_name)
            all_scores  = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)

            avg_by_map: dict = {}
            acc_by_map: dict = {}
            if not all_scores.empty:
                filtered = all_scores.loc[all_scores.apply(predicate, axis=1)]
                if not filtered.empty:
                    avg_by_map = (
                        filtered.groupby("beatmap_id")["score"].mean()
                        .round(0).astype(int).to_dict()
                    )
                    acc_by_map = (
                        filtered.groupby("beatmap_id")["accuracy"].mean()
                        .round(4).to_dict()
                    )

            pool_rows: dict = {}
            for _, row in map_stats.iterrows():
                bid = int(row["beatmap_id"])
                pool_rows.setdefault(bid, {})
                pool_rows[bid][row["step"]] = int(row["count"])

            split_by_bid: dict = {}
            for _, row in map_breakdown.iterrows():
                bid = int(row["beatmap_id"])
                split_by_bid[bid] = {
                    "picks_while_protected": int(row["picks_while_protected"]),
                    "protect_only":          int(row["protect_only"]),
                }

            code_by_bid = _build_map_code_lookup()
            order_by_bid = _build_map_order_lookup()
            mappool = [
                {
                    "beatmap_id":  bid,
                    "name":        code_by_bid.get(bid),
                    "pool_order":  order_by_bid.get(bid, 99999),
                    "picks":    counts.get("PICK", 0),
                    "bans":     counts.get("BAN", 0),
                    "protects": counts.get("PROTECT", 0),
                    "protects_picked": split_by_bid.get(bid, {}).get("picks_while_protected", 0),
                    "protects_unused": split_by_bid.get(bid, {}).get("protect_only", 0),
                    "avg_score":     avg_by_map.get(bid),
                    "avg_acc":       acc_by_map.get(bid),
                }
                for bid, counts in pool_rows.items()
            ]

            _, ascending = METHODS[method]
            metric_col = leaderboard.columns[-1]  # last col is always the metric

            # Per-player extras: avg score / acc, best score (with map + grade + acc).
            leaderboard_rows = leaderboard.to_dict(orient="records")
            if not all_scores.empty and leaderboard_rows:
                filt = all_scores.loc[all_scores.apply(predicate, axis=1)]
                if not filt.empty:
                    per_player = (
                        filt.groupby("user_id")
                            .agg(avg_score=("score", "mean"),
                                 avg_acc=("accuracy", "mean"))
                            .to_dict(orient="index")
                    )
                    best_idx = filt.groupby("user_id")["score"].idxmax()
                    best_rows = filt.loc[best_idx].set_index("user_id")
                    for r in leaderboard_rows:
                        uid = r["user_id"]
                        agg = per_player.get(uid, {})
                        r["avg_score"] = round(agg.get("avg_score", 0))
                        r["avg_acc"] = round(agg.get("avg_acc", 0), 4)
                        if uid in best_rows.index:
                            b = best_rows.loc[uid]
                            bid = int(b["beatmap_id"])
                            r["best"] = {
                                "beatmap_id": bid,
                                "name":       code_by_bid.get(bid),
                                "score":      int(b["score"]),
                                "accuracy":   round(float(b["accuracy"]), 4),
                                "rank":       (b["rank"] if pd.notna(b["rank"]) else None),
                                "mods":       (json.loads(b["mods"]) if pd.notna(b["mods"]) and b["mods"] else []),
                            }

            total_maps = len(mappool)
            return JSONResponse({
                "methods":    [{"key": k, "label": v[0]} for k, v in METHODS.items()],
                "method":     method,
                "ascending":  ascending,
                "metric_col": metric_col,
                "total_maps": total_maps,
                "leaderboard": leaderboard_rows,
                "mappool":     mappool,
            })

        @app.get("/api/stats/extras")
        async def api_stats_extras(count_failed: bool = True,
                                    pool_id: str | None = None,
                                    round_name: str | None = None,
                                    top_n: int = 20):
            from ..core.stats import include_all, exclude_failed
            predicate = include_all if count_failed else exclude_failed

            scores  = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            picks   = server.db.get_pick_actions(pool_id=pool_id, round_name=round_name)
            code_by_bid = _build_map_code_lookup()

            if scores.empty or picks.empty:
                return JSONResponse({
                    "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
                })

            scores = scores.loc[scores.apply(predicate, axis=1)].copy()
            if scores.empty:
                return JSONResponse({
                    "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
                })

            # Restrict to scores from pick events. game_scores.turn and
            # match_actions.turn use different counters, so join on
            # (match_id, beatmap_id) — a map is picked at most once per match.
            picks_key = picks[["match_id", "beatmap_id", "round_name"]].drop_duplicates(
                subset=["match_id", "beatmap_id"]
            )
            pick_scores = scores.merge(
                picks_key, on=["match_id", "beatmap_id"], how="inner"
            )
            if pick_scores.empty:
                return JSONResponse({
                    "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
                })

            # ── score diff per pick (closest / blowout) ──
            team_totals = (pick_scores
                .groupby(["match_id", "beatmap_id", "round_name",
                          "team_index", "team_name"], dropna=False)
                ["score"].sum()
                .reset_index())
            diffs = []
            for (mid, bid, rnd), grp in team_totals.groupby(
                    ["match_id", "beatmap_id", "round_name"], dropna=False):
                if len(grp) != 2:
                    continue  # only consider strict 2-team picks
                grp = grp.sort_values("team_index")
                a_row, b_row = grp.iloc[0], grp.iloc[1]
                a_score, b_score = int(a_row["score"]), int(b_row["score"])
                if a_score > b_score:
                    winner = "a"
                elif b_score > a_score:
                    winner = "b"
                else:
                    winner = "tie"
                diffs.append({
                    "match_id":   int(mid),
                    "round_name": rnd if pd.notna(rnd) else None,
                    "beatmap_id": int(bid),
                    "name":       code_by_bid.get(int(bid)),
                    "team_a":     a_score,
                    "team_b":     b_score,
                    "team_a_name": a_row["team_name"] if pd.notna(a_row["team_name"]) else None,
                    "team_b_name": b_row["team_name"] if pd.notna(b_row["team_name"]) else None,
                    "winner":     winner,
                    "diff":       abs(a_score - b_score),
                })

            closest  = sorted(diffs, key=lambda d: d["diff"])[:top_n]
            blowouts = sorted(diffs, key=lambda d: -d["diff"])[:top_n]

            # ── biggest carry performances ──
            map_stats = scores.groupby("beatmap_id")["score"].agg(["mean", "std"]).reset_index()
            pick_scores = pick_scores.merge(map_stats, on="beatmap_id", how="left")
            pick_scores["z"] = ((pick_scores["score"] - pick_scores["mean"]) /
                                pick_scores["std"]).fillna(0.0)

            team_z_avg = (pick_scores
                .groupby(["match_id", "beatmap_id", "team_index"])
                ["z"].mean()
                .reset_index().rename(columns={"z": "team_avg_z"}))
            pick_scores = pick_scores.merge(
                team_z_avg, on=["match_id", "beatmap_id", "team_index"]
            )
            # carry contribution: how much higher is the player's z vs their team's avg
            pick_scores["carry_z"] = pick_scores["z"] - pick_scores["team_avg_z"]

            top_carry = pick_scores.nlargest(top_n, "carry_z")
            carries = []
            for _, r in top_carry.iterrows():
                bid = int(r["beatmap_id"])
                mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                carries.append({
                    "match_id":   int(r["match_id"]),
                    "round_name": r["round_name"],
                    "user_id":    int(r["user_id"]),
                    "username":   r["username"],
                    "beatmap_id": bid,
                    "name":       code_by_bid.get(bid),
                    "mods":       mods,
                    "score":      int(r["score"]),
                    "accuracy":   round(float(r["accuracy"]), 4),
                    "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                    "z":          round(float(r["z"]), 3),
                    "team_avg_z": round(float(r["team_avg_z"]), 3),
                    "carry_z":    round(float(r["carry_z"]), 3),
                })

            # ── pp / z-pp top performances (rosu-pp-py required) ──
            highest_pp: list = []
            highest_zpp: list = []
            try:
                from ..core.stats import augment_pp
                aug = await augment_pp(pick_scores, db=server.db)
                if "pp" in aug.columns and aug["pp"].notna().any():
                    pp_df = aug.dropna(subset=["pp"]).copy()
                    pp_top = pp_df.nlargest(top_n, "pp")
                    for _, r in pp_top.iterrows():
                        bid = int(r["beatmap_id"])
                        mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                        highest_pp.append({
                            "match_id":   int(r["match_id"]),
                            "round_name": r["round_name"] if "round_name" in r and pd.notna(r["round_name"]) else None,
                            "user_id":    int(r["user_id"]),
                            "username":   r["username"],
                            "beatmap_id": bid,
                            "name":       code_by_bid.get(bid),
                            "mods":       mods,
                            "score":      int(r["score"]),
                            "accuracy":   round(float(r["accuracy"]), 4),
                            "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                            "pp":         round(float(r["pp"]), 1),
                        })

                    map_pp = pp_df.groupby("beatmap_id")["pp"].agg(["mean", "std"])
                    pp_df = pp_df.join(map_pp, on="beatmap_id", rsuffix="_map")
                    pp_df["zpp"] = ((pp_df["pp"] - pp_df["mean"]) / pp_df["std"]).fillna(0.0)
                    zpp_top = pp_df.nlargest(top_n, "zpp")
                    for _, r in zpp_top.iterrows():
                        bid = int(r["beatmap_id"])
                        mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                        highest_zpp.append({
                            "match_id":   int(r["match_id"]),
                            "round_name": r["round_name"] if "round_name" in r and pd.notna(r["round_name"]) else None,
                            "user_id":    int(r["user_id"]),
                            "username":   r["username"],
                            "beatmap_id": bid,
                            "name":       code_by_bid.get(bid),
                            "mods":       mods,
                            "score":      int(r["score"]),
                            "accuracy":   round(float(r["accuracy"]), 4),
                            "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                            "pp":         round(float(r["pp"]), 1),
                            "zpp":        round(float(r["zpp"]), 3),
                        })
            except Exception as e:
                logger.warning(f"pp augmentation failed: {e}")

            return JSONResponse({
                "closest_maps":     closest,
                "biggest_blowouts": blowouts,
                "biggest_carries":  carries,
                "highest_pp":       highest_pp,
                "highest_zpp":      highest_zpp,
            })

        @app.get("/api/stats/plot/{name}")
        async def api_stats_plot(name: str, format: str = "png", theme: str = "dark",
                                 count_failed: bool = True, beatmap_id: int | None = None,
                                 label: str | None = None,
                                 pool_id: str | None = None, round_name: str | None = None):
            try:
                from .. import plots as _plots
            except ImportError:
                _plots = None
            if _plots is None:
                return JSONResponse(
                    {"error": "plot rendering requires the [plots] extra (pip install -e '.[plots]')"},
                    status_code=501,
                )
            if format not in ("png", "hires", "svg"):
                return JSONResponse({"error": "format must be png|hires|svg"}, status_code=400)
            if name not in _plots.PLOTS:
                return JSONResponse(
                    {"error": f"unknown plot {name!r}; choose from {list(_plots.PLOTS)}"},
                    status_code=404,
                )
            theme = theme if theme in ("dark", "light") else "dark"

            scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            try:
                if name == "score_distribution":
                    if beatmap_id is None:
                        return JSONResponse({"error": "beatmap_id required"}, status_code=400)
                    if label is None:
                        label = _build_map_code_lookup().get(int(beatmap_id))
                    payload = _plots.score_distribution(
                        scores, int(beatmap_id), fmt=format, theme=theme,
                        exclude_failed=not count_failed, label=label,
                    )
                elif name == "pickban_heat":
                    payload = _plots.pickban_heat(
                        server.db.get_map_action_breakdown(pool_id=pool_id, round_name=round_name),
                        fmt=format, theme=theme,
                        code_by_bid=_build_map_code_lookup(),
                    )
                elif name == "consistency_scatter":
                    payload = _plots.consistency_scatter(
                        scores, fmt=format, theme=theme,
                        exclude_failed=not count_failed,
                    )
                else:
                    return JSONResponse({"error": f"unknown plot {name}"}, status_code=404)
            except Exception as e:
                logger.exception("plot %s failed", name)
                return JSONResponse({"error": str(e)}, status_code=500)

            media_type = "image/svg+xml" if format == "svg" else "image/png"
            ext = "svg" if format == "svg" else "png"
            headers = {}
            if format in ("hires", "svg"):
                headers["content-disposition"] = f'attachment; filename="{name}.{ext}"'
            from fastapi.responses import Response
            return Response(content=payload, media_type=media_type, headers=headers)

        @app.get("/api/stats/plot/consistency_scatter/data")
        async def api_stats_consistency_data(count_failed: bool = True,
                                             pool_id: str | None = None,
                                             round_name: str | None = None):
            try:
                from .. import plots as _plots
            except ImportError:
                return JSONResponse({"error": "plot module unavailable"}, status_code=501)
            scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            agg = _plots.consistency_aggregate(scores, exclude_failed=not count_failed)
            if agg.empty:
                return JSONResponse({"points": []})
            points = [
                {
                    "user_id": int(r["user_id"]),
                    "username": str(r["username"]),
                    "mean_z": float(r["mean_z"]),
                    "std_z": float(r["std_z"]),
                    "n": int(r["n"]),
                }
                for _, r in agg.iterrows()
            ]
            std_median = float(agg["std_z"].median()) if len(agg) > 1 else None
            return JSONResponse({"points": points, "std_median": std_median})

        @app.get("/api/stats/plots")
        async def api_stats_plot_list():
            try:
                from .. import plots as _plots
            except ImportError:
                _plots = None
            if _plots is None:
                return JSONResponse({"available": False, "plots": []})
            return JSONResponse({
                "available": True,
                "plots": [{"name": k, "label": v} for k, v in _plots.PLOTS.items()],
            })

        @app.get("/api/stats/filters")
        async def api_stats_filters():
            """Available pool / round combinations for the /stats filter UI.
            Pool ids are joined with their human-readable names from PoolStore.
            """
            opts = server.db.get_filter_options()
            pool_names = {p["id"]: p.get("name", p["id"]) for p in _POOL_STORE.list()}
            return JSONResponse({
                "pools":  [{"id": pid, "name": pool_names.get(pid, pid)} for pid in opts["pools"]],
                "rounds": opts["rounds"],
                "combos": opts["combos"],
            })

        @app.get("/api/stats/standings")
        async def api_stats_standings(count_failed: bool = True,
                                      pool_id: str | None = None,
                                      round_name: str | None = None):
            """Per-map top players and team standings.

            Returns:
              maps: list of {beatmap_id, name, players: [{rank, user_id, username,
                    score, accuracy, z, mods, rank_grade}], team_totals: [{team_name,
                    total_score, avg_z}]}
              has_teams: bool — True when team_index data is present
            """
            from ..core.stats import include_all, exclude_failed, z_sum_leaderboard
            predicate = include_all if count_failed else exclude_failed
            scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            code_by_bid = _build_map_code_lookup()

            if scores.empty:
                return JSONResponse({"maps": [], "has_teams": False})

            df = scores.loc[scores.apply(predicate, axis=1)].copy()
            if df.empty:
                return JSONResponse({"maps": [], "has_teams": False})

            # Deduplicate to best score per (player, map)
            df = df.sort_values("score", ascending=False).drop_duplicates(
                subset=["user_id", "beatmap_id"]
            )

            # Z-scores per map
            map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
            df = df.join(map_stats, on="beatmap_id")
            df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

            has_teams = df["team_name"].notna().any() if "team_name" in df.columns else False

            maps_out = []
            for bid, grp in df.groupby("beatmap_id"):
                top = grp.sort_values("score", ascending=False)
                players = []
                for rank_i, (_, r) in enumerate(top.iterrows(), 1):
                    mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                    players.append({
                        "rank":       rank_i,
                        "user_id":    int(r["user_id"]),
                        "username":   r["username"],
                        "score":      int(r["score"]),
                        "accuracy":   round(float(r["accuracy"]), 4),
                        "z":          round(float(r["z"]), 3),
                        "mods":       mods,
                        "rank_grade": (r["rank"] if pd.notna(r["rank"]) else None),
                    })

                team_totals = []
                if has_teams:
                    for tname, tgrp in grp.groupby("team_name"):
                        if pd.isna(tname):
                            continue
                        team_totals.append({
                            "team_name":   str(tname),
                            "total_score": int(tgrp["score"].sum()),
                            "avg_z":       round(float(tgrp["z"].mean()), 3),
                        })
                    team_totals.sort(key=lambda t: -t["total_score"])

                maps_out.append({
                    "beatmap_id":  int(bid),
                    "name":        code_by_bid.get(int(bid)),
                    "players":     players,
                    "team_totals": team_totals,
                })

            # Sort maps by pool order, falling back to pick count for unknown maps
            map_order = _build_map_order_lookup()
            map_stats_df = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
            pick_counts = {
                int(row["beatmap_id"]): int(row["count"])
                for _, row in map_stats_df.iterrows()
                if row["step"] == "PICK"
            }
            maps_out.sort(key=lambda m: (
                map_order.get(m["beatmap_id"], 99999),
                -pick_counts.get(m["beatmap_id"], 0),
            ))

            return JSONResponse({"maps": maps_out, "has_teams": bool(has_teams)})

        @app.get("/api/stats/results")
        async def api_stats_results(count_failed: bool = True,
                                    pool_id: str | None = None,
                                    round_name: str | None = None,
                                    method: str = "zscore",
                                    aggregate: str = "sum"):
            """Qualifiers-style team×map grid.

            Returns:
              teams: [{team_name, maps: {beatmap_id: {score, z, rank}}, total_z, avg_z}]
              map_order: [beatmap_id, ...]  — ordered by pool position / pick count
              has_data: bool
            """
            from ..core.stats import include_all, exclude_failed, METHODS, PP_METHODS, team_leaderboard
            if method not in METHODS:
                return JSONResponse({"error": f"unknown method: {method}"}, status_code=400)
            if method in PP_METHODS:
                return JSONResponse(
                    {"error": f"method {method!r} not yet supported on team-level results"},
                    status_code=400,
                )
            predicate = include_all if count_failed else exclude_failed
            scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            code_by_bid = _build_map_code_lookup()

            if scores.empty:
                return JSONResponse({"teams": [], "map_order": [], "has_data": False})

            df = scores.loc[scores.apply(predicate, axis=1)].copy()
            if df.empty or "team_name" not in df.columns or df["team_name"].isna().all():
                return JSONResponse({"teams": [], "map_order": [], "has_data": False})

            df = df.sort_values("score", ascending=False).drop_duplicates(
                subset=["user_id", "beatmap_id"]
            )

            # Team scores per map: sum of player scores on that map for that team
            team_map = (df.groupby(["team_name", "beatmap_id"])
                          .agg(total_score=("score", "sum"))
                          .reset_index())

            # Rank teams per map by total_score
            team_map["map_rank"] = team_map.groupby("beatmap_id")["total_score"].rank(
                ascending=False, method="min"
            ).astype(int)

            # Team-level metric: aggregate scores to (match, beatmap, team) team_score
            # first, then run the chosen metric over those team scores. Operating on
            # team totals matches the "sum first, then metric" tournament convention.
            agg_col = "mean" if aggregate == "mean" else "sum"
            team_lb = team_leaderboard(scores, method=method, include=predicate, aggregate=agg_col)
            metric_label, ascending = METHODS[method]
            metric_col = team_lb.columns[-1]

            # Build per-team map dict keyed by team_name
            teams_dict: dict[str, dict] = {}
            for _, r in team_map.iterrows():
                tname = r["team_name"]
                if pd.isna(tname):
                    continue
                if tname not in teams_dict:
                    teams_dict[tname] = {"team_name": str(tname), "maps": {}}
                bid = int(r["beatmap_id"])
                teams_dict[tname]["maps"][bid] = {
                    "total_score": int(r["total_score"]),
                    "map_rank":    int(r["map_rank"]),
                }

            for _, r in team_lb.iterrows():
                tname = r["username"]
                if tname in teams_dict:
                    val = float(r[metric_col])
                    teams_dict[tname]["total_metric"] = round(val, 3)
                    teams_dict[tname]["avg_metric"]   = round(val, 3)

            # sort by team metric (asc/desc per METHODS entry — placements is asc)
            sort_key = (lambda t: t.get("total_metric", 0)) if ascending \
                else (lambda t: -t.get("total_metric", 0))
            teams_out = sorted(teams_dict.values(), key=sort_key)

            # Map order: pool order, falling back to pick count
            map_order_lookup = _build_map_order_lookup()
            map_stats_df = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
            pick_counts = {
                int(row["beatmap_id"]): int(row["count"])
                for _, row in map_stats_df.iterrows()
                if row["step"] == "PICK"
            }
            all_bids = sorted(
                df["beatmap_id"].unique(),
                key=lambda b: (map_order_lookup.get(int(b), 99999), -pick_counts.get(int(b), 0))
            )
            map_order = [{"beatmap_id": int(b), "name": code_by_bid.get(int(b))} for b in all_bids]

            return JSONResponse({
                "teams":         teams_out,
                "map_order":     map_order,
                "method":        method,
                "metric_col":    metric_col,
                "metric_label":  metric_label,
                "aggregate":     agg_col,
                "ascending":     ascending,
                "has_data":      True,
            })

        @app.get("/api/stats/team_performances")
        async def api_stats_team_performances(count_failed: bool = True,
                                              pool_id: str | None = None,
                                              round_name: str | None = None):
            """Team-level performance table.

            Returns:
              teams: [{team_name, matches_played, wins, avg_z, avg_score,
                       maps_played, win_rate}]
            """
            from ..core.stats import include_all, exclude_failed
            predicate = include_all if count_failed else exclude_failed
            scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)

            # Team win/loss from matches table
            try:
                team_stats = server.db.get_team_stats()
            except Exception:
                team_stats = pd.DataFrame()

            if scores.empty:
                rows = []
                if not team_stats.empty:
                    for _, r in team_stats.iterrows():
                        rows.append({
                            "team_name":     r["team_name"],
                            "matches_played": int(r["matches_played"]),
                            "wins":           int(r["wins"]),
                            "win_rate":       round(int(r["wins"]) / max(int(r["matches_played"]), 1), 3),
                            "avg_z":          None,
                            "avg_score":      None,
                            "maps_played":    0,
                        })
                return JSONResponse({"teams": rows})

            df = scores.loc[scores.apply(predicate, axis=1)].copy()
            if df.empty or "team_name" not in df.columns or df["team_name"].isna().all():
                return JSONResponse({"teams": []})

            df = df.sort_values("score", ascending=False).drop_duplicates(
                subset=["user_id", "beatmap_id"]
            )

            map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
            df = df.join(map_stats, on="beatmap_id")
            df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

            team_agg = (df.groupby("team_name")
                          .agg(avg_z=("z", "mean"),
                               avg_score=("score", "mean"),
                               maps_played=("beatmap_id", "nunique"))
                          .reset_index())

            rows = []
            for _, r in team_agg.iterrows():
                tname = r["team_name"]
                if pd.isna(tname):
                    continue
                ws_row = team_stats[team_stats["team_name"] == tname] if not team_stats.empty else pd.DataFrame()
                matches = int(ws_row["matches_played"].iloc[0]) if not ws_row.empty else 0
                wins    = int(ws_row["wins"].iloc[0])           if not ws_row.empty else 0
                rows.append({
                    "team_name":      str(tname),
                    "matches_played": matches,
                    "wins":           wins,
                    "win_rate":       round(wins / max(matches, 1), 3),
                    "avg_z":          round(float(r["avg_z"]), 3),
                    "avg_score":      round(float(r["avg_score"])),
                    "maps_played":    int(r["maps_played"]),
                })

            rows.sort(key=lambda t: -t["avg_z"])
            return JSONResponse({"teams": rows})

        @app.get("/api/pools")
        async def list_pools():
            return JSONResponse(_POOL_STORE.list())

        @app.post("/api/pools")
        async def save_pool(request: Request):
            try:
                body = await request.json()
                pool_id = _POOL_STORE.save(body)
                return JSONResponse({"id": pool_id}, status_code=201)
            except ValueError as e:
                return JSONResponse({"error": str(e)}, status_code=400)
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.delete("/api/pools/{pool_id}")
        async def delete_pool(pool_id: str):
            if not _POOL_STORE.delete(pool_id):
                return JSONResponse({"error": "not found"}, status_code=404)
            return JSONResponse({"ok": True})

        @app.get("/api/beatmap/{beatmap_id}")
        async def get_beatmap(beatmap_id: str):
            """Fetch beatmap metadata from osu! API (cache-backed)."""
            try:
                meta = await get_beatmap_cache().fetch_one(int(beatmap_id))
            except Exception as e:
                logger.exception(f"failed to fetch beatmap {beatmap_id}")
                return JSONResponse({"error": str(e)}, status_code=500)
            if meta is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            # API response shape kept stable: web UI consumes `len`/`diff`.
            return JSONResponse({
                "id":            meta.get("id"),
                "beatmapset_id": meta.get("beatmapset_id"),
                "title":         meta.get("title", ""),
                "artist":        meta.get("artist", ""),
                "diff":          meta.get("version", ""),
                "len":           meta.get("total_length", 0),
                "stars":         meta.get("stars", 0.0),
                "ar":            meta.get("ar", 0.0),
                "od":            meta.get("od", 0.0),
                "cs":            meta.get("cs", 0.0),
                "hp":            meta.get("hp", 0.0),
            })

        @app.get("/api/beatmap/{beatmap_id}/attributes")
        async def get_beatmap_attributes(beatmap_id: str, mods: str = ""):
            """Fetch beatmap difficulty attributes with mods from osu! API."""
            from ..client import make_client
            from aiosu.models import Mods
            client = make_client()
            try:
                # Parse mods string to Mods object
                mods_obj = Mods(mods) if mods else None
                attrs = await client.get_beatmap_attributes(int(beatmap_id), mods=mods_obj)
                return JSONResponse({
                    "star_rating": round(attrs.star_rating, 2),
                    "max_combo": attrs.max_combo,
                    "ar": round(attrs.approach_rate, 1) if attrs.approach_rate else None,
                    "od": round(attrs.overall_difficulty, 1) if attrs.overall_difficulty else None,
                })
            except Exception as e:
                logger.exception(f"failed to fetch beatmap attributes {beatmap_id} with mods {mods}")
                return JSONResponse({"error": str(e)}, status_code=500)
            finally:
                await client.aclose()

        @app.get("/api/matches")
        async def api_matches():
            all_matches = (
                [server._pending_summary(mid, p) for mid, p in server._pending.items()] +
                [m.summary() for m in server._matches.values()]
            )
            return JSONResponse(all_matches)

        @app.post("/api/matches")
        async def create_match(request: Request):
            try:
                body = await request.json()
                match_id = str(uuid.uuid4())[:8]
                server._pending[match_id] = body
                server._notify_landing()
                return JSONResponse({"id": match_id, "status": "pending"}, status_code=201)
            except Exception as e:
                logger.exception("failed to create match")
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.post("/api/matches/{match_id}/start")
        async def start_match(match_id: str, request: Request):
            payload = server._pending.pop(match_id, None)
            if payload is None:
                return JSONResponse({"error": "not found or already started"}, status_code=404)
            try:
                iface = await server._create_match(payload, match_id=match_id)
                return JSONResponse({"id": iface.match_id, "status": "running"})
            except Exception as e:
                server._pending[match_id] = payload  # restore on failure
                logger.exception("failed to start match")
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.delete("/api/matches/{match_id}")
        async def delete_match(match_id: str):
            if match_id in server._pending:
                del server._pending[match_id]
                server._notify_landing()
                return JSONResponse({"ok": True})
            iface = server._matches.get(match_id)
            if iface is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            if iface._lobby:
                await iface._lobby.handle_input(">close force", "web")
            return JSONResponse({"ok": True})

        @app.websocket("/ws/landing")
        async def ws_landing(websocket: WebSocket):
            await websocket.accept()
            server._landing_clients.add(websocket)
            await websocket.send_text(json.dumps({
                "type": "matches",
                "matches": [m.summary() for m in server._matches.values()],
            }))
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                server._landing_clients.discard(websocket)

        @app.get("/match/{match_id}")
        async def match_view(match_id: str):
            return FileResponse(self.static_dir / "index.html")

        @app.websocket("/ws/{match_id}")
        async def ws_match(websocket: WebSocket, match_id: str):
            await websocket.accept()
            iface = server._matches.get(match_id)
            if iface is None:
                await websocket.send_text(json.dumps({"type": "error", "message": "match not found"}))
                await websocket.close(code=4004)
                return
            iface._clients.add(websocket)
            if iface._last_state:
                try:
                    await websocket.send_text(json.dumps({"type": "state", **iface._last_state}))
                except Exception:
                    pass
            try:
                while True:
                    text = await websocket.receive_text()
                    if iface._lobby:
                        await iface._lobby.handle_input(text, "web")
            except WebSocketDisconnect:
                pass
            finally:
                iface._clients.discard(websocket)

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        srv = uvicorn.Server(config)
        logger.info("web server at http://%s:%d", self.host, self.port)
        await srv.serve()
