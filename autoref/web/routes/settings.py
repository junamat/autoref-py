"""GET /api/settings and PUT /api/settings routes."""
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

_VALID_MODES = {"off", "assisted", "auto"}
_VALID_TEAM_MODES = {0, 2}
_TIMER_FIELDS = {
    "timer_pick", "timer_ban", "timer_protect", "timer_ready_up",
    "timer_start_map", "timer_force_start", "timer_between_maps", "timer_closing",
}


def _validate(body: dict) -> list[str]:
    errors = []
    if "port" in body:
        try:
            p = int(body["port"])
            if not (1 <= p <= 65535):
                errors.append("port must be 1–65535")
        except (TypeError, ValueError):
            errors.append("port must be an integer")
    if "default_mode" in body and body["default_mode"] not in _VALID_MODES:
        errors.append(f"default_mode must be one of {_VALID_MODES}")
    if "default_prefix" in body:
        p = body["default_prefix"]
        if not isinstance(p, str) or len(p) != 1:
            errors.append("default_prefix must be a single character")
    if "default_refs" in body and not isinstance(body["default_refs"], list):
        errors.append("default_refs must be a list")
    if "default_best_of" in body:
        try:
            if int(body["default_best_of"]) < 1:
                errors.append("default_best_of must be ≥1")
        except (TypeError, ValueError):
            errors.append("default_best_of must be an integer")
    if "default_team_mode" in body:
        try:
            if int(body["default_team_mode"]) not in _VALID_TEAM_MODES:
                errors.append(f"default_team_mode must be one of {_VALID_TEAM_MODES}")
        except (TypeError, ValueError):
            errors.append("default_team_mode must be an integer")
    for tf in _TIMER_FIELDS:
        if tf in body:
            try:
                if int(body[tf]) < 0:
                    errors.append(f"{tf} must be ≥0")
            except (TypeError, ValueError):
                errors.append(f"{tf} must be an integer")
    return errors


def register(app: FastAPI, server: "WebServer") -> None:
    from dataclasses import fields as dc_fields

    from ...core.config import _SECRET_FIELDS, to_api
    from ...core.config import save as save_config

    _config_field_names = {f.name for f in dc_fields(server.config.__class__)}

    @app.get("/api/settings")
    async def get_settings():
        """Return current server configuration, redacting secret fields."""
        return JSONResponse(to_api(server.config))

    @app.put("/api/settings")
    async def put_settings(request: Request):
        """Update server configuration and return requires_restart flag."""
        body: dict[str, Any] = await request.json()

        errors = _validate(body)
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        old_host = server.config.host
        old_port = server.config.port

        for key, val in body.items():
            if key not in _config_field_names:
                continue
            if key in _SECRET_FIELDS:
                if val == "" or val is None:
                    continue
            setattr(server.config, key, val)

        save_config(server.db, server.config)

        requires_restart = (
            server.config.host != old_host or server.config.port != old_port
        )
        return JSONResponse({"requires_restart": requires_restart})
