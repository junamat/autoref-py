# core — always available
from .core.enums import WinCondition, MapState, Step, RefMode
from .core.models import PlayableMap, Pool, ModdedPool, Team, Ruleset, Match, Timers, NO_MODS, OrderScheme
from .core.storage import MatchDatabase
from .core.pool_store import PoolStore
from .core.lobby import Lobby, MatchResult, PlayerResult, SlotInfo
from .core.output import OutputSink
from .core.score_fetcher import ScoreFetcher
from .core.stats import leaderboard, z_sum_leaderboard, include_all, exclude_failed, METHODS
from .core.base import AutoRef

# controllers — always available (depend only on core)
from .controllers.bracket import BracketAutoRef, Phase
from .controllers.qualifiers import QualifiersAutoRef

# factory — package-level glue for dict payloads (web/CLI/Discord)
from .factory import build_autoref, flatten_pool_tree

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

# optional: stat plots (requires matplotlib + scipy)
try:
    from . import plots as plots
except ImportError:
    plots = None  # type: ignore
