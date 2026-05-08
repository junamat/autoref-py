# core — always available
# controllers — always available (depend only on core)
from .controllers.bracket import BracketAutoRef, Phase
from .controllers.qualifiers import QualifiersAutoRef
from .controllers.voted import VotedQualifiersAutoRef
from .core.enums import MapState, RefMode, Step, WinCondition
from .core.lobby import Lobby, MatchResult, PlayerResult, SlotInfo
from .core.models import NO_MODS, Match, ModdedPool, OrderScheme, PlayableMap, Pool, Ruleset, Team, Timers
from .core.output import OutputSink
from .core.pool_store import PoolStore
from .core.ref import AutoRef
from .core.score_fetcher import ScoreFetcher
from .core.stats import (
    METHODS,
    PP_METHODS,
    augment_pp,
    exclude_failed,
    include_all,
    leaderboard,
    leaderboard_async,
    pp_leaderboard,
    z_pp_leaderboard,
    z_sum_leaderboard,
)
from .core.storage import MatchDatabase

# factory — package-level glue for dict payloads (web/CLI/Discord)
from .factory import build_autoref, flatten_pool_tree

# optional: web UI (requires fastapi + uvicorn)
try:
    from .web.server import WebInterface, WebServer
except ImportError:
    pass

# optional: beatmap cache (requires aiosu)
try:
    from .core.beatmap_cache import BeatmapCache, get_beatmap_cache
except ImportError:
    pass

# optional: local pp calculator (requires rosu-pp-py)
try:
    from .core.pp_calc import compute_pp
except ImportError:
    pass

# optional: stat plots (requires matplotlib + scipy)
try:
    from . import plots as plots
except ImportError:
    plots = None  # type: ignore
