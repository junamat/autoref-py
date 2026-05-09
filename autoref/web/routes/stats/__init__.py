from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from ...server import WebServer

from . import context, extras, filters, leaderboard, plots, results, standings, team_performances


def register(app: FastAPI, server: "WebServer") -> None:
    leaderboard.register(app, server)
    extras.register(app, server)
    plots.register(app, server)
    filters.register(app, server)
    context.register(app, server)
    standings.register(app, server)
    results.register(app, server)
    team_performances.register(app, server)
