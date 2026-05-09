"""TypedDict response shapes for all API routes (V48)."""
from .beatmap import BeatmapResponse
from .match import MatchSummary
from .pool import PoolDetail, PoolSummary
from .stats import BestScore, LeaderboardRow, MapPoolRow
from .user import AccountResponse, UserResponse

__all__ = [
    "BeatmapResponse",
    "MatchSummary",
    "PoolDetail",
    "PoolSummary",
    "BestScore",
    "LeaderboardRow",
    "MapPoolRow",
    "AccountResponse",
    "UserResponse",
]
