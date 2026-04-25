"""Start the web server standalone (no Bancho connection required)."""
import asyncio
from autoref.web import WebInterface

if __name__ == "__main__":
    asyncio.run(WebInterface().start())
