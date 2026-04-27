# Pool Builder

The pool builder is a web interface for creating, managing, and organizing tournament mappools. Access it at `/pool-builder` when the web server is running.

## Quick Start

1. Start the web server: `python server.py`
2. Navigate to `http://localhost:8000/pool-builder`
3. Build your pool using the interface
4. Click **save pool** to persist it

## Features

### Building Pools

**Add Pool/Mod Group**
- Click **+ pool** to create a new mod group (NM, HD, HR, etc.)
- Set the mod group name, mods, and win condition
- Pools can be nested for organization

**Add Maps**
- Click **+ map** to add a beatmap
- Enter the beatmap ID or paste an osu! URL
- The system automatically fetches metadata from the osu! API:
  - Song title and artist
  - Difficulty name
  - Length (in seconds)
  - Star rating
- Set map-specific properties:
  - **Code**: Map identifier (e.g., NM1, HD2)
  - **Tiebreaker**: Mark as TB map
  - **Disallowed**: Prevent picking (for banned maps)
  - **Mods**: Override pool mods for this map
  - **Win Condition**: Override pool win condition
- Click **🔄 refresh** to update beatmap data from the API

### Import & Export

**⬆ Import**
- Paste beatmap IDs or URLs, one per line
- Format: `<beatmap_id> <pool_name>` (e.g., `3814680 NM`)
- If pool name is omitted, uses the default pool specified in the dialog
- Maps are automatically grouped by pool name
- Beatmap metadata (title, artist, difficulty, length, stars) is fetched from the osu! API during import

**⬇ Export**
- Downloads a `.txt` file with all maps
- Format: `<beatmap_id> <pool_name>` (one per line)
- Can be re-imported without modification

### Pool Management

**📂 Load / Manage**
- View all saved pools
- Click a pool to load it for editing
- Click 🗑 to delete a pool (with confirmation)

**💾 Save**
- Saves the current pool to the database
- If editing an existing pool, updates it
- Otherwise creates a new pool
- URL updates with pool ID for sharing

### Composing & Separating

**🔗 Compose**
- Merge multiple saved pools into the current pool
- Select pools with checkboxes
- Click **merge selected** to combine them
- Useful for building complete pools from modular components (e.g., combine separate NM, HD, HR pools)

**✂ Separate**
- Extract pools from the current tree and save them separately
- Select pools to extract with checkboxes
- Click **extract selected** to:
  - Save each as a new pool file
  - Remove them from the current tree
  - Auto-name as `<parent pool> - <pool name>`
- Useful for breaking down large pools into reusable components

## Workflow Examples

### Building a Tournament Pool from Scratch

1. Click **+ pool** and name it "NM"
2. Click **+ map** repeatedly to add NoMod maps
3. Repeat for HD, HR, DT, FM pools
4. Click **save pool** and name it "Tournament X Mappool"

### Building Modular Pools

1. Create and save separate pools: "NM Pool", "HD Pool", "HR Pool"
2. Start a new pool
3. Click **🔗 compose**
4. Select all three pools
5. Click **merge selected**
6. Save as "Complete Tournament Pool"

### Reusing Pool Components

1. Load a complete tournament pool
2. Click **✂ separate**
3. Select the NM and HD pools
4. Click **extract selected**
5. These are now saved separately for reuse in other tournaments

### Importing from a List

1. Copy beatmap IDs from a spreadsheet or document
2. Click **⬆ import**
3. Paste the list
4. Specify pool names in the format `<id> <pool>` or set a default pool
5. Click **lookup & import**

## Technical Details

### Data Structure

Pools are stored as a tree structure:

```javascript
{
  id: "unique-id",
  name: "Tournament Pool",
  tree: [
    {
      id: "pool-id",
      type: "pool",
      name: "NM",
      mods: "",
      winCon: "score_v2",
      open: true,
      children: [
        {
          id: "map-id",
          type: "map",
          code: "NM1",
          bid: "3814680",
          title: "Song Title",
          diff: "[Difficulty]",
          len: 180,
          stars: 5.5,
          tb: false,
          disallowed: false,
          mods: "",
          winCon: "inherit"
        }
      ]
    }
  ]
}
```

### API Endpoints

- `GET /api/pools` - List all saved pools
- `POST /api/pools` - Save a pool (create or update)
- `DELETE /api/pools/{pool_id}` - Delete a pool
- `GET /api/beatmap/{beatmap_id}` - Fetch beatmap metadata from osu! API
- `GET /api/beatmap/{beatmap_id}/attributes?mods={mods}` - Fetch difficulty attributes with mods

### Beatmap Data

When importing maps or clicking the refresh button, the system fetches:
- **Title & Artist**: Full song name
- **Difficulty**: Difficulty version name
- **Length**: Total length in seconds
- **Stars**: Difficulty rating (rounded to 2 decimals)

When mods are set on a map, the star rating automatically updates to reflect the modded difficulty using the osu! API's `/beatmaps/{id}/attributes` endpoint.

Data is fetched from the osu! API v2 and cached in the pool structure.

### Storage

Pools are stored in `~/.local/share/autoref/pools.json` as a JSON object mapping pool IDs to pool data.

### Win Conditions

- `score_v2` - ScoreV2 (default)
- `score` - Classic score
- `accuracy` - Accuracy percentage
- `combo` - Max combo

### Mod Options

Common presets: `NM`, `HD`, `HR`, `DT`, `FL`, `EZ`, `FM`, `HDHR`, `HDDT`

Custom mods can be entered manually (e.g., `HDHRDT`).
