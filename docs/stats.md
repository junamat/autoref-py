# Stats

The stats page shows cross-match leaderboards and mappool usage data. Access it at `/stats` when the web server is running.

## Quick Start

1. Start the web server: `python server.py`
2. Navigate to `http://localhost:8080/stats`
3. Select a calculation method, failed score filter, and aggregate mode
4. Click **↻ reload** to refresh

Data is populated automatically as matches are played and saved to the database.

## Features

### Leaderboard

Ranks players across all recorded matches using the selected calculation method. Each row shows:
- **rank** — position (top 3 highlighted)
- **player** — username
- **maps** — number of unique maps played
- **metric** — the calculated value with a proportional bar

### Mappool Statistics

Shows pick/ban/protect counts and average score per beatmap, sorted by total activity:
- **map** — beatmap ID
- **picks** — times picked
- **bans** — times banned
- **protects** — times protected
- **avg score** — mean score across all plays (respects the failed score filter)

### Calculation Methods

Select how player performance is scored across maps. The method toggle is populated from the API.

| Key | Label | Description | Missing scores |
|---|---|---|---|
| `zscore` | Z-Sum | Z = (score − map mean) / map std; std=0 → Z=0 | excluded |
| `avg_score` | Average Score | Mean score across all maps; aggregate setting ignored | counted as 0 |
| `placements` | Avg Sum of Placements | Sum of per-map ranks (1 = best); lower is better | excluded |
| `percentile` | Percentile | Z-scores → percentiles via normal CDF `0.5 × (1 + erf(z / √2))`; values 0–1 | excluded |
| `zipf` | Zipf's Law | `100 / (rank + correction)` where `correction = 1.4 × num_maps`; higher is better | excluded |
| `pct_diff` | Percent Difference | `(score − min) / (max − min)` scaled to 0–100; min==max → 50 | excluded |

### Failed Scores

- **include** — count failed scores in all calculations (default)
- **exclude** — drop rows where the player failed the map before calculating

### Aggregate

Controls how per-map metrics are combined into a single player score:
- **sum** — add up the per-map values (default)
- **mean** — average the per-map values

Note: `avg_score` always computes a mean regardless of this setting.

## Workflow Examples

### Comparing Players After a Tournament

1. Navigate to `/stats`
2. Select **Z-Sum** for a normalized cross-map comparison
3. Set failed scores to **exclude** if failed plays should not count
4. Use **mean** aggregate if players played different numbers of maps

### Identifying Hot and Cold Maps

1. Navigate to `/stats`
2. Scroll to the **mappool statistics** section
3. Maps are sorted by total activity (picks + bans + protects)
4. High ban counts indicate maps teams want to avoid; high pick counts indicate popular maps

## Technical Details

### Score Deduplication

Before any calculation, scores are deduplicated to the best score per `(player, map)` pair across all matches. A player who played the same map in multiple matches only contributes their highest score.

### Data Source

All calculations run over the `game_scores` table in the SQLite database. Scores are enriched from the osu! API by `ScoreFetcher` after each map — they include score, accuracy, max combo, mods, pass/fail, and rank.

The database path defaults to `matches.db` in the working directory. Override with the `$AUTOREF_DB` environment variable.

### API Endpoint

`GET /api/stats` — returns leaderboard and mappool data.

Query parameters:
- `method` — calculation method key (default: `zscore`)
- `count_failed` — include failed scores, `true` or `false` (default: `true`)
- `aggregate` — `sum` or `mean` (default: `sum`)

Response shape:

```json
{
  "methods": [{"key": "zscore", "label": "Z-Sum"}, "..."],
  "method": "zscore",
  "ascending": false,
  "metric_col": "z_sum",
  "leaderboard": [
    {"user_id": 123, "username": "player", "maps_played": 10, "z_sum": 4.2134},
    "..."
  ],
  "mappool": [
    {"beatmap_id": 3814680, "picks": 5, "bans": 2, "protects": 1, "avg_score": 850000},
    "..."
  ]
}
```
