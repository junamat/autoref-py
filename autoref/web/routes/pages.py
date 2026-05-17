"""Static HTML page routes."""
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from ...core.auth import current_user

    def _is_restricted(request: Request) -> bool:
        """True when user is unauthenticated or has player role."""
        user = current_user(request, server.db)
        return user is None or user.role == "player"

    @app.get("/")
    async def index():
        return FileResponse(server.static_dir / "index.html")

    @app.get("/ref")
    async def ref_dashboard(request: Request):
        if _is_restricted(request):
            return RedirectResponse("/stats", status_code=302)
        return FileResponse(server.static_dir / "ref.html")

    @app.get("/pool-builder")
    async def pool_builder(request: Request):
        if _is_restricted(request):
            return RedirectResponse("/stats", status_code=302)
        return FileResponse(server.static_dir / "pool_builder.html")

    @app.get("/stats")
    async def stats_page():
        return FileResponse(server.static_dir / "stats.html")

    @app.get("/match/{match_id}")
    async def match_view(match_id: str, request: Request):
        if _is_restricted(request):
            return RedirectResponse("/stats", status_code=302)
        return FileResponse(server.static_dir / "ref.html")

    @app.get("/settings")
    async def settings_page(request: Request):
        if _is_restricted(request):
            return RedirectResponse("/stats", status_code=302)
        return FileResponse(server.static_dir / "settings.html")

    @app.get("/matches/new")
    async def matches_new_page(request: Request):
        if _is_restricted(request):
            return RedirectResponse("/stats", status_code=302)
        return FileResponse(server.static_dir / "matches_new.html")

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
