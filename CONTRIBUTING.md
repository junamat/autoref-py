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
autoref/core/        # AutoRef ABC, data models, lobby, storage, stats
autoref/controllers/ # BracketAutoRef, QualifiersAutoRef, factory
autoref/web/         # FastAPI server + vanilla JS frontend
scripts/             # dev utilities (seed_db.py, stats_poc.py)
tests/               # pytest suite
```

## Architecture rules

- `core/` has no dependency on `controllers/` or `web/`. Keep it that way.
- `controllers/` may import from `core/` only.
- `web/` may import from both; it is the only layer allowed to depend on FastAPI/uvicorn.
- New match types go in `controllers/` as a subclass of `AutoRef`.
- New commands belong in `core/commands.py` (`COMMANDS` list) — that's the single source of truth for the web UI and `>help`.

## Commits

```
<type>: <short imperative description>
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`. One logical change per commit. No PR to `main` without passing tests.
