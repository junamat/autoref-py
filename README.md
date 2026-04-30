# autoref-py

![tests](https://github.com/junamat/autoref-py/actions/workflows/tests.yml/badge.svg)

IRC-based osu! tournament auto-referee. Handles pick/ban/protect sequences, qualifiers pools, and timers — with an optional web dashboard.

# readme status

OUTDATED
---

## Project layout

```
autoref/
  core/           # Abstract base class, data models, lobby, storage — framework internals
  controllers/    # BracketAutoRef, QualifiersAutoRef — extend these for custom match types
  web/            # FastAPI web interface (optional extra)
  client.py       # osu! API v2 client helper

server.py         # Start the web server standalone (no Bancho connection required)
run_bracket.py    # Example: BO13 bracket match
run_qualifiers.py # Example: sequential qualifiers lobby
```

## Install

```bash
# Core only (IRC bot, no web UI)
pip install -e "."

# With web interface
pip install -e ".[web]"

# Everything (recommended for development)
pip install -e ".[all]"
```

Requires Python ≥ 3.11 and a `.env` file with:
```
BANCHO_USERNAME=...
BANCHO_PASSWORD=...
CLIENT_ID=...
CLIENT_SECRET=...
```

---

## Status

### Done
- ~~Classes / data structures~~ — `Pool`, `Match`, `Ruleset`, `Team`, `Timers`, `OrderScheme`
- ~~Core match logic~~ — pick / ban / protect / tiebreaker state machine
- ~~Bracket controller~~ — `BracketAutoRef`: roll → order → protect → ban → pick → TB
- ~~Qualifiers controller~~ — `QualifiersAutoRef`: sequential pool, multi-run, ETA, N teams
- ~~Ref modes~~ — `AUTO` / `ASSISTED` / `OFF`, `!panic`, `>mode` / `>next` / `>dismiss`
- ~~IO — text / CLI interface~~
- ~~IO — web interface~~ — chat, score strip, mappool, timeline, players, settings, commands tabs
- ~~Web: qualifiers view~~ — maps left, played, ETA, per-map durations from osu! API
- ~~Web: assisted-mode banner~~ — confirm / change / dismiss proposal flow
- ~~Web: landing page~~ — active match list, join button, ref pill
- ~~Web: start a match from the browser~~ — quick-start form with per-team player input
- ~~Web: mappool builder~~ — standalone `/pool-builder`, save/load, selectable in match form
- ~~Beatmap cache~~ — disk-backed JSON at `~/.cache/autoref/beatmaps.json`
- ~~Match persistence~~ — `MatchDatabase` (SQLite) - not set in stone
- ~~Score enrichment~~ — background `ScoreFetcher` polls the osu! match endpoint for mods/acc/combo/rank per game
- ~~Project structure~~ — `core/` / `controllers/` / `web/` split; modular `pyproject.toml` extras
- ~~Stats page (cross-match)~~ — `/stats`: configurable leaderboard, mappool table, score-distribution KDE per map, pick/ban/protect heat (with protect→pick overlay), interactive player-consistency scatter; SVG + hi-res PNG exports
- ~~Per-round stats~~ — matches are tagged with `pool_id` + `round_name` (schema + match-creation form); `/stats` exposes round / pool selectors that re-filter every chart and the leaderboard

### Planned
- Cross-round stats when rounds share a pool — auto-detect pool equivalence (same beatmap set) and aggregate matches across compatible rounds
- Cross-pool stats — needs an abstraction layer (mod-class / difficulty bucket / star-range) so scores from different pools can be normalised before aggregation
- Safe multi-ref support — credential handling, sign-in flow
- IO — Discord interface
- CI stat badge
- will to live (impossible)

---

## Quick start

```python
from autoref import BracketAutoRef, Match, Pool, PlayableMap, Ruleset, Team, Timers
from autoref import WinCondition, RefMode, Step
import bancho, asyncio

ar = BracketAutoRef(client, match, "room name", mode=RefMode.AUTO)
asyncio.run(ar.run())
```

See [`run_bracket.py`](run_bracket.py) and [`run_qualifiers.py`](run_qualifiers.py) for full working examples.
