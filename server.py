"""Start the web server standalone (no Bancho connection required)."""
import asyncio
import signal
from autoref.web import WebServer

async def main():
    server = WebServer()
    
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        print("\nShutting down gracefully...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server_task = asyncio.create_task(server.start())
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    
    done, pending = await asyncio.wait(
        [server_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Cancel all running match tasks
    for task in server._tasks.values():
        task.cancel()
    
    await asyncio.gather(*server._tasks.values(), return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
