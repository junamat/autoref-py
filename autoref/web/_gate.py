from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_ALLOWED_PATHS = {
    "/setup",
    "/login",
    "/api/setup",
    "/api/auth/login",
    "/api/auth/callback",
}


class SetupGateMiddleware(BaseHTTPMiddleware):
    """Block all routes with 503 when no users exist, except setup/auth paths."""

    def __init__(self, app, db):
        super().__init__(app)
        self._db = db
        self._done = False  # cached True once first user exists

    async def dispatch(self, request, call_next):
        if self._done:
            return await call_next(request)
        path = request.url.path
        if path.startswith("/static/") or path in _ALLOWED_PATHS:
            return await call_next(request)
        count = self._db._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            return JSONResponse({"error": "setup_required"}, status_code=503)
        self._done = True
        return await call_next(request)
