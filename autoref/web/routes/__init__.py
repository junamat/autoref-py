"""Route registration fanout for the web server."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from ..server import WebServer


def register_all(app: "FastAPI", server: "WebServer") -> None:
    from . import pages, stats, pool, match, ws
    pages.register(app, server)
    stats.register(app, server)
    pool.register(app, server)
    match.register(app, server)
    ws.register(app, server)
