"""Server-wide configuration stored in the `settings` table."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields, asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import MatchDatabase

_SECRET_FIELDS = {"bancho_password", "osu_client_secret"}

_ENV_MAP: dict[str, tuple[str, type]] = {
    "BANCHO_USERNAME":          ("bancho_username",        str),
    "BANCHO_PASSWORD":          ("bancho_password",        str),
    "CLIENT_ID":                ("osu_client_id",          str),
    "CLIENT_SECRET":            ("osu_client_secret",      str),
    "AUTOREF_HOST":             ("host",                   str),
    "AUTOREF_PORT":             ("port",                   int),
    "AUTOREF_DEFAULT_MODE":     ("default_mode",           str),
    "AUTOREF_DEFAULT_PREFIX":   ("default_prefix",         str),
    "AUTOREF_DEFAULT_REFS":     ("default_refs",           list),
    "AUTOREF_DEFAULT_BEST_OF":  ("default_best_of",        int),
    "AUTOREF_DEFAULT_TEAM_MODE":("default_team_mode",      int),
    "AUTOREF_TIMER_PICK":       ("timer_pick",             int),
    "AUTOREF_TIMER_BAN":        ("timer_ban",              int),
    "AUTOREF_TIMER_PROTECT":    ("timer_protect",          int),
    "AUTOREF_TIMER_READY_UP":   ("timer_ready_up",         int),
    "AUTOREF_TIMER_START_MAP":  ("timer_start_map",        int),
    "AUTOREF_TIMER_FORCE_START":("timer_force_start",      int),
    "AUTOREF_TIMER_BETWEEN_MAPS":("timer_between_maps",    int),
    "AUTOREF_TIMER_CLOSING":    ("timer_closing",          int),
}


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    bancho_username: str = ""
    bancho_password: str = ""
    osu_client_id: str = ""
    osu_client_secret: str = ""
    default_mode: str = "off"
    default_prefix: str = "!"
    default_refs: list[str] = field(default_factory=list)
    default_best_of: int = 1
    default_team_mode: int = 0
    timer_pick: int = 120
    timer_ban: int = 120
    timer_protect: int = 120
    timer_ready_up: int = 90
    timer_start_map: int = 5
    timer_force_start: int = 10
    timer_between_maps: int = 5
    timer_closing: int = 30


def _from_env() -> dict[str, object]:
    """Read Config fields from env vars. Returns only keys that are set."""
    out: dict[str, object] = {}
    for env_key, (attr, typ) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        if typ is list:
            out[attr] = [v.strip() for v in val.split(",") if v.strip()]
        elif typ is int:
            try:
                out[attr] = int(val)
            except ValueError:
                pass
        else:
            out[attr] = val
    return out


def load(db: "MatchDatabase") -> Config:
    rows = db._conn.execute("SELECT key, value FROM settings").fetchall()
    if not rows:
        env_vals = _from_env()
        cfg = Config(**{k: v for k, v in env_vals.items() if k in {f.name for f in fields(Config)}})
        save(db, cfg)
        return cfg
    data: dict[str, object] = {}
    for key, raw in rows:
        try:
            data[key] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data[key] = raw
    valid_fields = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in valid_fields})


def save(db: "MatchDatabase", cfg: Config) -> None:
    d = asdict(cfg)
    db._conn.executemany(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [(k, json.dumps(v)) for k, v in d.items()],
    )
    db._conn.commit()


def to_api(cfg: Config) -> dict:
    """Serialize Config for GET /api/settings — secrets redacted."""
    d = asdict(cfg)
    for secret in _SECRET_FIELDS:
        is_set = bool(d.pop(secret, ""))
        d[f"{secret}_set"] = is_set
    return d
