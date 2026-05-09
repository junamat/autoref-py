from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


@dataclass(slots=True)
class OsuUser:
    id: int
    username: str


def _redirect_uri(config: "Config") -> str:
    host = config.host if config.host not in ("0.0.0.0", "") else "localhost"
    return f"http://{host}:{config.port}/api/auth/callback"


def authorize_url(config: "Config") -> str:
    if not config.osu_client_id:
        raise ValueError("osu_client_id not configured")
    from aiosu.models.scopes import Scopes
    from aiosu.utils.auth import generate_url
    return generate_url(
        client_id=int(config.osu_client_id),
        redirect_uri=_redirect_uri(config),
        scopes=Scopes.IDENTIFY,
    )


async def exchange_code(code: str, config: "Config") -> OsuUser:
    from aiosu.utils.auth import process_code
    from aiosu.v2 import Client

    token = await process_code(
        client_id=int(config.osu_client_id),
        client_secret=config.osu_client_secret,
        redirect_uri=_redirect_uri(config),
        code=code,
    )
    async with Client(token=token) as client:
        user = await client.get_me()
    return OsuUser(id=user.id, username=user.username)
