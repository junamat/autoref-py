"""MatchPersister: writes finalized match to MatchDatabase."""
import logging

from ..models import Match
from ..storage import MatchDatabase

logger = logging.getLogger(__name__)


class MatchPersister:
    def __init__(self, db: MatchDatabase | None):
        self.db = db

    def save(self, match: Match, winner_index: int | None) -> None:
        if self.db is None:
            return
        try:
            self.db.save_match(match, winner_index)
            logger.info("match saved (id=%s)", match.match_id)
        except Exception:
            logger.exception("failed to save match")
