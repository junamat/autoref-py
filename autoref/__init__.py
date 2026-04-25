# core — always available
from .core.enums import WinCondition, MapState, Step, RefMode
from .core.models import PlayableMap, Pool, ModdedPool, Team, Ruleset, Match, Timers, NO_MODS, OrderScheme
from .core.storage import MatchDatabase
from .core.lobby import Lobby, MatchResult, PlayerResult, SlotInfo
from .core.output import OutputSink
from .core.base import AutoRef

# controllers — always available (depend only on core)
from .controllers.bracket import BracketAutoRef, Phase
from .controllers.qualifiers import QualifiersAutoRef

# optional: web UI (requires fastapi + uvicorn)
try:
    from .web.server import WebInterface, WebServer
except ImportError:
    pass

# optional: beatmap cache (requires aiosu)
try:
    from .core.beatmap_cache import BeatmapCache
except ImportError:
    pass
