# Stats

The stats page shows cross-match leaderboards, mappool usage, qualifier-style results, per-map standings, team performances and "extras" (closest maps, blowouts, top carries, top pp/z-pp plays). Access it at `/stats` when the web server is running.

## Quick Start

1. Start the web server: `python server.py`
2. Navigate to `http://localhost:8080/stats`
3. (Optional) pick a pool and/or round from the filter bar
4. Select a calculation method, failed-score filter, and aggregate mode
5. Click **↻ reload** to refresh

Data populates automatically as matches are played and saved to the database.

## Tabs

- **Performances** *(default)* — per-player leaderboard + mappool table
- **Results** — qualifier-style team × map grid (team totals per map, sorted by team metric)
- **Standings** — per-map top players + team totals per map
- **Mappool** — pick / ban / protect counts and average score per beatmap
- **Extras** — closest maps, biggest blowouts, biggest carry performances, top pp / top z-pp plays

## Features

### Leaderboard (Performances)

Ranks players across all recorded matches using the selected calculation method. Each row shows:
- **rank** — position (top 3 highlighted)
- **player** — username
- **maps** — number of unique maps played
- **avg score / avg acc** — mean score and mean accuracy across all plays (respects the failed-score filter)
- **best** — the player's single highest score, with map code, mods, accuracy and grade
- **metric** — the calculated value with a proportional bar

### Mappool Statistics

Per-beatmap activity, sorted by total picks/bans/protects:
- **map** — beatmap ID + pool code (when known)
- **picks** — times picked
- **bans** — times banned
- **protects** — times protected (further split into `protects_picked` and `protects_unused` in the JSON)
- **avg score / avg acc** — mean score and accuracy across all plays (respects the failed-score filter)

### Results (Qualifier Grid)

Team × map matrix. Each cell is the sum of player scores on that map for that team, with a per-map rank. Rows are sorted by the team-level metric (the chosen calculation method run on summed team scores, not on per-player metrics).

### Standings

For each map: top players (with score, accuracy, mods, z-score and grade) and, when team data is present, total team score + team avg z-score per map.

### Team Performances

Per-team aggregate: matches played, wins, win rate, avg z-score, avg score, maps played. Sorted by avg z-score.

### Extras

- **closest maps** — picked maps with the smallest score gap between the two teams
- **biggest blowouts** — picked maps with the largest gap
- **biggest carries** — individual plays where the player's z-score most exceeds their team's average z on that map
- **highest pp** / **highest z-pp** — top single plays by raw pp / per-map z-pp; only present when the `[pp]` extra is installed (`rosu-pp-py`)

### Graphs

A "graphs" section appears below the tables when the `[plots]` extra is installed (`pip install -e ".[plots]"`). Three plots are rendered server-side via matplotlib + scipy:

- **Score distribution** — per-map histogram + KDE of passing scores. Pick a beatmap from the dropdown. Vertical lines mark μ and μ ± σ; the title shows `n` (sample size) and number of fails filtered out.
- **Pick / ban / protect heat** — stacked horizontal bars per beatmap, sorted by total activity. Quickly shows which maps were contested vs. ignored.
- **Player consistency** — scatter of per-player mean z-score (x) vs. stddev of z-scores (y). Top-right = high-skill / high-variance (carries on their pick); top-left = consistent high-skill (hardest to scout). Top 5 are labeled. The underlying points are also exposed at `/api/stats/plot/consistency_scatter/data` for client-side rendering.

Each graph block has **SVG** and **HQ PNG** download buttons. Default display PNG is 144 DPI / ~800px wide; the HQ download is 300 DPI / ~1800px wide. SVGs scale cleanly.

If matplotlib/scipy aren't installed, the graphs section is hidden silently and the stats page still works.

### Calculation Methods

Select how player performance is scored across maps. The method toggle is populated from the API.

| Key | Label | Sort | Description | Missing scores |
|---|---|---|---|---|
| `zscore` | Z-Score | desc | Z = (score − map mean) / map std; std=0 → Z=0 | excluded |
| `avg_score` | Average Score | desc | Mean score across all maps; aggregate setting ignored | counted as 0 |
| `placements` | Placements | asc | Sum of per-map ranks (1 = best); lower is better | excluded |
| `percentile` | Percentile | desc | Z-scores → percentiles via normal CDF `0.5 × (1 + erf(z / √2))`; 0–1 | excluded |
| `zipf` | Zipf's Law | desc | `100 / (rank + correction)` where `correction = 1.4 × num_maps`; higher is better | excluded |
| `pct_diff` | Percent Difference | desc | `(score − min) / (max − min) × 100`; min==max → 50 | excluded |
| `mc_flashlight` | Match Cost (Flashlight) | desc | `mean(score / map_median) × cbrt(n_player / m_median)` | excluded |
| `mc_bathbot` | Match Cost (Bathbot) | desc | Per-match cost with participation + mod variety + tiebreaker bonus, then aggregated across matches | excluded |
| `beta_dist` | Beta Distribution | desc | Per-map fit Beta(α,β) on min-max-normalized scores via method of moments; player metric = Beta CDF. Requires `scipy` | excluded |
| `pp` | Performance Points | desc | Raw pp computed locally via `rosu-pp-py`. Requires `[pp]` extra | excluded |
| `z_pp` | Z-PP | desc | Z = (pp − map mean pp) / map std pp. Requires `[pp]` extra | excluded |

### Failed Scores

- **include** — count failed scores in all calculations (default)
- **exclude** — drop rows where the player failed the map before calculating

### Aggregate

Controls how per-map metrics are combined into a single player score:
- **sum** — add up the per-map values (default)
- **mean** — average the per-map values

Notes:
- `avg_score` always computes a mean regardless of this setting.
- `mc_flashlight` produces one cost per player and ignores aggregate.
- `mc_bathbot` defaults to `mean` across matches.

### Pool / Round Filters

Most endpoints accept optional `pool_id` and `round_name` query parameters. The `/api/stats/filters` endpoint exposes the available pools, rounds and valid combinations, plus per-pool default method/aggregate/count_failed settings (`stats_defaults` on a pool).

## Workflow Examples

### Comparing Players After a Tournament

1. Navigate to `/stats`
2. Select **Z-Score** for a normalized cross-map comparison
3. Set failed scores to **exclude** if failed plays should not count
4. Use **mean** aggregate if players played different numbers of maps

### Identifying Hot and Cold Maps

1. Open the **Mappool** tab
2. Maps are sorted by total activity (picks + bans + protects)
3. High ban counts → maps teams want to avoid; high pick counts → popular maps; high `protects_picked` → contested high-value picks

## Technical Details

### Score Deduplication

Before any calculation, scores are deduplicated to the best score per `(player, map)` pair across all matches. A player who played the same map in multiple matches only contributes their highest score.

### Team Aggregation

Team-level metrics (`/api/stats/results`) first sum per-player scores into per-team-per-map totals (`aggregate_to_teams`), then run the chosen leaderboard method over those team totals. Team metrics never average per-player metrics; they always operate on the summed team score.

### Data Source

Calculations run over the `game_scores` table in the SQLite database. Scores are enriched from the osu! API by `ScoreFetcher` after each map — they include score, accuracy, max combo, mods, pass/fail, and rank. The `pp` / `z_pp` methods additionally require `rosu-pp-py` (the `[pp]` extra); computed pp values are cached back into `game_scores.pp` keyed by the score row's `id` and the rosu-pp version, so subsequent calls are DB reads.

The database path defaults to `matches.db` in the working directory. Override with the `$AUTOREF_DB` environment variable.

### Module Layout

The stats engine lives in `autoref/core/stats/`:

- `methods.py` — per-method leaderboard implementations + `METHODS` registry + `PP_METHODS` set + `augment_pp`
- `aggregate.py` — `aggregate_to_teams`, `team_leaderboard`
- `predicates.py` — `ScorePredicate`, `include_all`, `exclude_failed`
- `leaderboard.py` — sync `leaderboard()` dispatcher and async `leaderboard_async()` (use the async one for `pp` / `z_pp`)

### API Endpoints

#### `GET /api/stats`

Returns the per-player leaderboard + mappool data shown on the **Performances** tab.

Query parameters:
- `method` — calculation method key (default: `zscore`)
- `count_failed` — `true` (default) or `false`
- `aggregate` — `sum` (default) or `mean`
- `pool_id`, `round_name` — optional filters

Response shape:

```json
{
  "methods":    [{"key": "zscore", "label": "Z-Score"}, "..."],
  "method":     "zscore",
  "ascending":  false,
  "metric_col": "z_sum",
  "total_maps": 14,
  "leaderboard": [
    {
      "user_id": 123, "username": "player", "maps_played": 10, "z_sum": 4.21,
      "avg_score": 712345, "avg_acc": 0.9712,
      "best": {"beatmap_id": 3814680, "name": "NM1", "score": 980000,
               "accuracy": 0.9912, "rank": "S", "mods": ["HD"]}
    }
  ],
  "mappool": [
    {"beatmap_id": 3814680, "name": "NM1", "pool_order": 0,
     "picks": 5, "bans": 2, "protects": 1,
     "protects_picked": 1, "protects_unused": 0,
     "avg_score": 850000, "avg_acc": 0.9821}
  ]
}
```

The metric column name varies by method (`z_sum`, `avg_score`, `placement_sum`, `percentile_sum`, `zipf_sum`, `pct_diff_sum`, `mc_flashlight`, `mc_bathbot`, `beta_dist`, `pp`, `z_pp`).

#### `GET /api/stats/extras`

Closest maps, biggest blowouts, biggest carries, highest pp/z-pp plays.

Query parameters: `count_failed`, `pool_id`, `round_name`, `top_n` (default `20`).

Response keys: `closest_maps`, `biggest_blowouts`, `biggest_carries`, `highest_pp`, `highest_zpp` (the last two are empty unless `rosu-pp-py` is available).

#### `GET /api/stats/standings`

Per-map top players and team totals.

Query parameters: `count_failed`, `pool_id`, `round_name`.

Response: `{"maps": [...], "has_teams": bool}`.

#### `GET /api/stats/results`

Qualifier-style team × map grid driven by the team-level metric.

Query parameters: `count_failed`, `pool_id`, `round_name`, `method`, `aggregate`. Rejects `pp` / `z_pp` (not supported on team-level results yet).

Response keys: `teams`, `map_order`, `method`, `metric_col`, `metric_label`, `aggregate`, `ascending`, `has_data`.

#### `GET /api/stats/team_performances`

Per-team aggregate row: matches played, wins, win rate, avg z, avg score, maps played.

Query parameters: `count_failed`, `pool_id`, `round_name`.

#### `GET /api/stats/filters`

Available pool / round combinations + per-pool defaults + the method registry.

Response shape:

```json
{
  "pools":  [{"id": "pool_a", "name": "Pool A"}],
  "rounds": ["QF", "SF", "GF"],
  "combos": [{"pool_id": "pool_a", "round_name": "QF"}],
  "pool_defaults": {"pool_a": {"method": "zscore", "aggregate": "sum", "count_failed": true}},
  "methods": [{"key": "zscore", "label": "Z-Score"}, "..."]
}
```

#### `GET /api/stats/plots`

Discoverability for graphs. Returns `{"available": bool, "plots": [{"name", "label"}, ...]}`. `available=false` when the `[plots]` extra isn't installed.

#### `GET /api/stats/plot/{name}`

Render a graph. `name ∈ {score_distribution, pickban_heat, consistency_scatter}`.

Query parameters:
- `format` — `png` (default, ~800px), `hires` (300 DPI download), `svg` (vector download)
- `theme` — `dark` (default) or `light`
- `count_failed` — passes through to `exclude_failed` for distribution / scatter plots
- `beatmap_id` — required for `score_distribution`
- `label` — optional override for the map label on `score_distribution`
- `pool_id`, `round_name` — optional filters

Returns the encoded image with a `content-disposition: attachment` header for `hires`/`svg`. Returns 501 with a JSON error body if matplotlib/scipy aren't installed.

#### `GET /api/stats/plot/consistency_scatter/data`

Raw data behind the consistency scatter for client-side rendering.

Query parameters: `count_failed`, `pool_id`, `round_name`.

Response: `{"points": [{"user_id", "username", "mean_z", "std_z", "n"}, ...], "std_median": float | null}`.
