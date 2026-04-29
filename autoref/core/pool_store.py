"""PoolStore: persistent disk-backed registry of saved mappools.

Stores the pool-builder tree as a JSON object, one entry per pool ID.
Default path: ~/.cache/autoref/pools.json (override via the constructor).
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_POOLS_FILE = Path.home() / ".cache" / "autoref" / "pools.json"


class PoolStore:
    """Read/write wrapper around the pools.json file.

    Each saved pool is a dict with at least {"id", "name", "tree"}; the
    tree is the pool-builder representation consumed by
    `autoref.factory.flatten_pool_tree`.
    """

    def __init__(self, path: Path = _DEFAULT_POOLS_FILE):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, pools: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(pools, indent=2))

    def list(self) -> list[dict]:
        return list(self._read().values())

    def get(self, pool_id: str) -> dict | None:
        return self._read().get(pool_id)

    def save(self, pool: dict) -> str:
        """Save or overwrite a pool. Returns the assigned ID.

        Uses pool["id"] if present, else slugifies pool["name"]. Mutates
        the stored copy to include the resolved ID.
        """
        name = (pool.get("name") or "").strip()
        if not name:
            raise ValueError("pool name required")
        pool_id = pool.get("id") or name.lower().replace(" ", "_")
        pools = self._read()
        pools[pool_id] = {**pool, "id": pool_id}
        self._write(pools)
        return pool_id

    def delete(self, pool_id: str) -> bool:
        pools = self._read()
        if pool_id not in pools:
            return False
        del pools[pool_id]
        self._write(pools)
        return True
