"""MatchScorer: pure formatters over Match state. No I/O, no async."""
from ..models import Match
from ..utils import find_map as _find_map


class MatchScorer:
    def __init__(self, match: Match):
        self.match = match

    def team_name(self, team_index: int) -> str:
        if team_index < len(self.match.teams):
            return self.match.teams[team_index].name
        return str(team_index)

    def format_step_history(self, step_name: str) -> str:
        ms = self.match.match_status
        if ms.empty:
            return "none"
        rows = ms[ms["step"] == step_name]
        if rows.empty:
            return "none"
        parts = []
        for _, row in rows.iterrows():
            pm = _find_map(self.match, int(row["beatmap_id"]))
            code = pm.name if pm and pm.name else str(row["beatmap_id"])
            parts.append(f"{self.team_name(int(row['team_index']))} {code}")
        return ", ".join(parts)

    def format_scoreline(self, wins: list[int]) -> str:
        bo = self.match.ruleset.best_of
        needed = bo // 2 + 1
        if len(wins) == 2:
            return (f"{self.team_name(0)} {wins[0]} : {wins[1]} {self.team_name(1)}"
                    f" (BO{bo}, first to {needed})")
        return " | ".join(f"{self.team_name(i)}: {wins[i]}" for i in range(len(wins)))

    def winner_index(self, wins: list[int]) -> int | None:
        needed = self.match.ruleset.wins_needed
        for i, w in enumerate(wins):
            if w >= needed:
                return i
        return None
