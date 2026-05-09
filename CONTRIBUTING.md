# Contributing

## Setup

```bash
git clone https://github.com/junamat/autoref-py
cd autoref-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env  # fill in BANCHO_USERNAME, BANCHO_PASSWORD, CLIENT_ID, CLIENT_SECRET
```

## Running tests

```bash
pytest tests/
```

Tests are fully offline — no Bancho or osu! API connection required.

## Project layout

```
autoref/core/
  models/            # per-class domain models (Match, Pool, PlayableMap, Team, …)
  db/                # SQLite layer: migrations, schema SQL, per-table repos
  ref/               # AutoRef ABC + lobby helpers (announcer, broker, persister, …)
  stats/
    leaderboards/    # one module per leaderboard algorithm + DISPATCH dict
  config.py          # Config dataclass, load/save, env-seed
  auth.py            # User dataclass, session helpers
  oauth.py           # osu! OAuth authorize_url + exchange_code
  pool_store.py      # disk-backed pool registry (~/.cache/autoref/pools.json)
autoref/controllers/ # BracketAutoRef, QualifiersAutoRef, VotedQualifiersAutoRef
autoref/web/
  routes/
    stats/           # per-endpoint modules (leaderboard, extras, plots, …)
  schemas/           # TypedDict response shapes (BeatmapResponse, MatchSummary, …)
  serializers/       # pure domain→DTO mapping fns (no I/O)
  static/            # vanilla JS frontend
  server.py          # WebServer + WebInterface
autoref/plots/       # per-plot modules (consistency, score_dist, …)
autoref/factory.py   # build_autoref(payload) — package-level glue
autoref/client.py    # osu! API v2 client factory (no import-time side effects)
scripts/             # dev utilities (seed_db.py, stats_poc.py)
tests/               # pytest suite (fully offline)
```

## Architecture rules

- `core/` has no dependency on `controllers/`, `web/`, or `client.py`. Hydration helpers (`PlayableMap.create`, `Team.create`, `BeatmapCache.prefetch`) accept an `aiosu.v2.Client`; if omitted they lazy-import `autoref.client.make_client` only at call time, so importing `core/` triggers no I/O or env reads.
- `controllers/` may import from `core/` only.
- `web/` may import from `core/`, `controllers/`, `factory`, `client`. It is the only layer allowed to depend on FastAPI/uvicorn.
- `factory.py` lives at the package root since it is consumed by both web and any future CLI/Discord glue. It depends on `core/`, `controllers/`, `client`.
- New match types go in `controllers/` as a subclass of `AutoRef`.
- New commands belong in `core/commands.py` (`COMMANDS` list) — that's the single source of truth for the web UI and `>help`.
- API response shapes belong in `web/schemas/` as TypedDicts. Route handlers must not construct inline response dicts for shapes shared by 2+ routes or that expose domain model fields (primitive one-offs like `{"ok": True}` are exempt).
- Domain→DTO mapping belongs in `web/serializers/` as pure functions (no I/O, no side effects). Route handlers call one serializer per response.

## Commits

```
<type>: <short imperative description>
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`. One logical change per commit. No PR to `main` without passing tests.
