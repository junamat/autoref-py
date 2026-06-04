"""Import osu! multiplayer matches from mp links into the database.

Usage:
    python run_mp_import.py <mp_link> [<mp_link> ...]
    python run_mp_import.py --pool POOL_ID --round ROUND_NAME <mp_link> ...

Examples:
    python run_mp_import.py https://osu.ppy.sh/mp/123456
    python run_mp_import.py https://osu.ppy.sh/mp/123456 https://osu.ppy.sh/mp/789012
    python run_mp_import.py --pool finals --round ro16 https://osu.ppy.sh/mp/123456

Requires .env with CLIENT_ID, CLIENT_SECRET
"""
import argparse
import asyncio
import logging
import sys
from os import getenv

from dotenv import load_dotenv

from autoref.core.db import MatchDatabase
from autoref.core.mp_importer import import_mp_links

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Import osu! multiplayer matches from mp links",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "links",
        nargs="+",
        help="osu! mp links (e.g. https://osu.ppy.sh/mp/123456)",
    )
    parser.add_argument(
        "--pool",
        default=None,
        help="Pool ID to tag matches with (for stats filtering)",
    )
    parser.add_argument(
        "--round",
        default=None,
        dest="round_name",
        help="Round name to tag matches with (for stats filtering)",
    )
    parser.add_argument(
        "--db",
        default=getenv("AUTOREF_DB", "matches.db"),
        help=f"Database path (default: {getenv('AUTOREF_DB', 'matches.db')})",
    )
    args = parser.parse_args()

    db = MatchDatabase(args.db)

    async def run():
        return await import_mp_links(
            db,
            args.links,
            pool_id=args.pool,
            round_name=args.round_name,
        )

    try:
        imported_ids = asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("\nInterrupted.")
        sys.exit(1)
    except Exception:
        logger.exception("Import failed")
        sys.exit(1)
    finally:
        db.close()

    if imported_ids:
        logger.info(f"Successfully imported {len(imported_ids)} match(es): {imported_ids}")
    else:
        logger.warning("No matches were imported")
        sys.exit(1)


if __name__ == "__main__":
    main()
