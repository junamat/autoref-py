# autoref-py

![tests](https://github.com/junamat/autoref-py/actions/workflows/tests.yml/badge.svg)

IRC-based osu! tournament auto-referee. Handles pick/ban/protect sequences, qualifiers pools, and timers — with an optional web dashboard.

---

## Install

```bash
pip install -e ".[all]"   # everything, recommended
pip install -e ".[web]"   # core + web UI
pip install -e "."        # core only (IRC bot, no web UI)
```

Requires Python ≥ 3.11. Create a `.env` in the project root:

```
BANCHO_USERNAME=your_osu_username
BANCHO_PASSWORD=your_irc_password      # from https://osu.ppy.sh/p/irc
CLIENT_ID=...                          # osu! API v2 app
CLIENT_SECRET=...
```

---

## Quickstart — just run it

Copy `run_bracket.py` or `run_qualifiers.py`, set your player names and beatmap IDs, and run:

```bash
python run_bracket.py
```

The web dashboard opens at **http://localhost:8080**. From there you can monitor the match, send commands, and see the mappool live.

Set the ref mode with the `AUTOREF_MODE` env var before running:

```bash
AUTOREF_MODE=auto python run_bracket.py    # fully automatic
AUTOREF_MODE=assisted python run_bracket.py  # bot proposes, ref confirms
AUTOREF_MODE=off python run_bracket.py     # ref drives everything
```

Any player can type `!panic` in the lobby at any time to drop to OFF mode.

---

## Use cases

### 1 — I just want it to work, no customisation

Use the web UI. Start the server:

```bash
python server.py
```

Go to **http://localhost:8080**, fill in the quick-start form, hit **create**. The match appears in the list as pending. Hit **start** when you're ready to connect to Bancho.

Build your mappool at **/pool-builder** first — paste beatmap IDs, group them by mod, save. The pool will appear in the match creation form.

---

### 2 — I want defaults but need to change the obvious stuff

Edit the top of `run_bracket.py`. The things you'll actually touch are all at the top:

```python
# Pool — swap beatmap IDs and names
POOL = Pool("Grand Finals",
    Pool("NM",
        PlayableMap(1234567, name="NM1"),
        PlayableMap(2345678, name="NM2"),
        ...
    ),
    ModdedPool("HD", aiosu.models.mods.Mods("HD"),
        PlayableMap(3456789, name="HD1"),
        ...
    ),
    Pool("TB",
        PlayableMap(9999999, name="TB", is_tiebreaker=True),
    ),
)

# Format
RULESET = Ruleset(
    vs=1,                          # players per team (1v1, 2v2, ...)
    best_of=11,                    # BO11, BO9, etc.
    bans_per_team=2,
    protects_per_team=1,
    ...
)

# Timers (seconds)
TIMERS = Timers(
    between_maps=10,
    ready_up=60,
    force_start=10,
)
```

For qualifiers, edit `run_qualifiers.py` the same way — just the pool and team name.

**Common env vars:**

| Variable | Default | Effect |
|---|---|---|
| `AUTOREF_MODE` | `off` | `auto` / `assisted` / `off` |
| `AUTOREF_REFS` | *(anyone)* | Comma-separated osu! usernames allowed to use ref commands |
| `AUTOREF_PREFIX` | `>` | Command prefix in chat |
| `TEAM_RED_PLAYER` | `Dario` | Red team player username |
| `TEAM_BLUE_PLAYER` | `junamat` | Blue team player username |

---

### 3 — I need to tweak things for my tournament

**Custom ban/protect order (ABBA, ABAB, loser-picks, etc.)**

```python
from autoref import OrderScheme

scheme = OrderScheme(
    "my_format",
    protect_first=0,    # 0 = roll winner, 1 = roll loser
    ban_first=1,        # loser bans first
    pick_first=0,       # winner picks first
    ban_pattern="ABBA", # or "ABAB"
)

# Multiple schemes = roll winner chooses
RULESET = Ruleset(..., schemes=[scheme_a, scheme_b])
```

**Split bans (ban some before picks, rest after N picks)**

```python
scheme = OrderScheme("split", split_ban_after_pick=1)
# 2 bans before picks, 2 bans after the 1st pick
```

**Asymmetric bans/protects per team**

```python
Ruleset(..., bans_per_team=[2, 1], protects_per_team=[1, 0])
# team 0 gets 2 bans, team 1 gets 1
```

**Multiple teams (N > 2)**

Override `next_picker` in a `BracketAutoRef` subclass — the default only handles 2 teams.

**Restrict who can use ref commands**

```python
ar = BracketAutoRef(..., refs={"junamat", "nagi"})
# only those two can use > commands; anyone can still !panic and >timeout
```

**Custom timers per phase**

```python
TIMERS = Timers(
    pick=90,
    ban=120,
    protect=60,
    between_maps=15,
    force_start=5,
    closing=30,
)
```

**Running multiple matches at once**

```python
server = WebServer()
for match_data in my_matches:
    ar, client = await build_autoref(match_data, ...)
    iface = WebInterface()
    iface.attach(ar.lobby)
    iface.attach_autoref(ar)
    server.register(iface)

await server.start()
```

---

### 4 — I want to change the match logic

Subclass `BracketAutoRef` or `QualifiersAutoRef` and override what you need.

**Custom win condition per map**

```python
class MyAutoRef(BracketAutoRef):
    def _map_winner(self, result):
        # e.g. accuracy-based: highest average accuracy wins
        ...
```

**Custom pick order (e.g. loser always picks)**

```python
class LoserPicksAutoRef(BracketAutoRef):
    def next_picker(self, match_status) -> int:
        if self._last_map_winner is None:
            return self._rank_to_team(self.scheme.pick_first)
        return 1 - self._last_map_winner  # loser of last map picks
```

**Custom phase sequence**

Override `next_step` entirely. It receives the match status DataFrame and returns `(team_index, Step)`:

```python
class DraftAutoRef(BracketAutoRef):
    def next_step(self, match_status):
        # your own state machine
        if ...:
            return (team, Step.BAN)
        return (team, Step.PICK)
```

**Custom announce messages**

```python
class MyAutoRef(BracketAutoRef):
    async def announce_pick(self, team_index, beatmap_id):
        pm = _find_map(self.match, beatmap_id)
        await self.lobby.say(f"🎵 {self.match.teams[team_index].name} picked {pm.name}!")

    async def announce_ban(self, team_index, beatmap_id):
        ...
```

**Add custom ref commands**

```python
from autoref.core.commands import Command, COMMANDS

class MyAutoRef(BracketAutoRef):
    def _commands(self):
        return super()._commands() + [
            Command("reroll", desc="re-roll team order", section="bracket", bracket_only=True),
        ]

    async def _dispatch_command(self, cmd, args, source):
        if cmd == "reroll":
            self.ranking = None
            await self._run_roll_phase()
            return True
        return await super()._dispatch_command(cmd, args, source)
```

**Hook into state changes** (e.g. post to Discord)

```python
async def on_state(state: dict):
    # called after every pick/ban/protect/win
    print(f"score: {state['wins']}")

ar.add_state_hook(on_state)
```

---

### 5 — I want to build something on top of this

**Start a match programmatically (no web UI)**

```python
from autoref.controllers.factory import build_autoref

ar, client = await build_autoref({
    "type": "bracket",
    "room_name": "QF: Red vs Blue",
    "mode": "auto",
    "best_of": 9,
    "bans_per_team": 2,
    "protects_per_team": 1,
    "teams": [
        {"name": "Red",  "players": ["cookiezi"]},
        {"name": "Blue", "players": ["vaxei"]},
    ],
    "maps": [
        {"beatmap_id": 1234567, "name": "NM1", "mod_group": "NM"},
        {"beatmap_id": 2345678, "name": "HD1", "mod_group": "HD", "mods": "HD"},
        {"beatmap_id": 9999999, "name": "TB",  "mod_group": "TB", "is_tiebreaker": True},
    ],
}, bancho_username="...", bancho_password="...")

await client.connect()
await ar.run()
```

**Attach a Discord bot as a ref**

```python
# Register a reply sink so >help output goes to a DM, not the lobby
ar.lobby.register_reply_sink("discord", my_discord_dm_fn)

# Route Discord messages into the command system
await ar.lobby.handle_input(">mode auto", source="discord")
```

**Persist and query match history**

```python
from autoref import MatchDatabase

db = MatchDatabase("matches.db")
ar = BracketAutoRef(..., db=db)
# match is saved automatically on >close

history = db.get_match_history()
map_stats = db.get_map_stats()
```

---

## Ref commands

Commands are sent in the lobby chat (prefix `>`) or via the web dashboard.

| Command | Scope | Description |
|---|---|---|
| `!panic` | anyone | Instantly switch to OFF mode |
| `>timeout [secs]` | anyone | Pause for 120s (or custom) |
| `>status` / `>st` | anyone | Show current score and phase |
| `>scoreline` / `>sc` | anyone | Score only |
| `>mode <auto\|assisted\|off>` | ref | Switch ref mode |
| `>next <map>` | ref | Confirm pick/ban/protect (assisted/off) |
| `>undo` / `>u` | ref | Undo last action |
| `>abort` / `>ab` | ref | Abort map and replay |
| `>dismiss` | ref | Discard pending proposal |
| `>close [force]` | ref | End match (saves unless force) |
| `>startmap [delay]` | ref | Force-start the map |
| `>setmap <id>` | ref | Change the map |
| `>invite` / `>inv` | ref | Re-invite all players |
| `>setscoreline <s0> <s1>` | ref | Override the score |
| `>roll <t1> <t2>` | ref | Set roll ranking manually |
| `>order <n>` | ref | Choose an order scheme |
| `>fp/fb/fpro <team>` | ref | Set who goes first for pick/ban/protect |

---

## Project layout

```
autoref/
  core/
    models.py        # Pool, PlayableMap, Match, Ruleset, Team, Timers, OrderScheme
    base.py          # AutoRef ABC — state machine, command dispatch, await logic
    commands.py      # Command dataclass + COMMANDS registry
    lobby.py         # Lobby — thin wrapper over BanchoLobby
    enums.py         # WinCondition, MapState, Step, RefMode
    storage.py       # MatchDatabase (SQLite)
    score_fetcher.py # Background score enrichment from osu! API
    beatmap_cache.py # Disk-backed beatmap metadata cache
  controllers/
    bracket.py       # BracketAutoRef — roll/order/protect/ban/pick/TB
    qualifiers.py    # QualifiersAutoRef — sequential pool, multi-run, ETA
    factory.py       # build_autoref() — create a match from a plain dict
  web/
    server.py        # WebServer + WebInterface
    static/          # Vanilla JS single-page app

run_bracket.py       # Working example: BO13 1v1 Finals
run_qualifiers.py    # Working example: solo qualifiers lobby
server.py            # Start web server standalone (no Bancho connection)
```
