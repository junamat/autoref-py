"""Static HTML page routes."""
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import FileResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/")
    async def index():
        return FileResponse(server.static_dir / "index.html")

    @app.get("/pool-builder")
    async def pool_builder():
        return FileResponse(server.static_dir / "pool_builder.html")

    @app.get("/stats")
    async def stats_page():
        return FileResponse(server.static_dir / "stats.html")

    @app.get("/match/{match_id}")
    async def match_view(match_id: str):
        return FileResponse(server.static_dir / "index.html")

    @app.get("/settings")
    async def settings_page():
        return FileResponse(server.static_dir / "settings.html")

    @app.get("/login")
    async def login_page():
        return FileResponse(server.static_dir / "login.html")

    @app.get("/setup")
    async def setup_page():
        return FileResponse(server.static_dir / "setup.html")

    @app.get("/account")
    async def account_page():
        return FileResponse(server.static_dir / "account.html")

    @app.get("/users")
    async def users_page():
        return FileResponse(server.static_dir / "users.html")
