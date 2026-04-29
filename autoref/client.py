from os import getenv
import aiosu

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
