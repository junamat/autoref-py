from os import getenv

import aiosu
from aiosu.exceptions import RefreshTokenExpiredError

_DOTENV_LOADED = False


def _ensure_dotenv() -> None:
    """Load .env once on first client construction. Idempotent and side-effect-free at import time."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    _DOTENV_LOADED = True


def make_client() -> aiosu.v2.Client:
    _ensure_dotenv()
    return aiosu.v2.Client(
        client_id=getenv("CLIENT_ID"),
        client_secret=getenv("CLIENT_SECRET"),
    )


async def safe_api_call(func, *args, **kwargs):
    """Execute an API call with automatic logout on token expiration.
    
    Catches RefreshTokenExpiredError and returns None to signal the caller
    should log the user out.
    """
    try:
        return await func(*args, **kwargs)
    except RefreshTokenExpiredError:
        return None
    except Exception:
        raise
