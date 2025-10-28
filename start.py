"""
Startup script to run both API server and data collector.
"""
import asyncio
import uvicorn
import structlog
from multiprocessing import Process
from src.main import main as collector_main

logger = structlog.get_logger()


def run_api():
    """Run FastAPI server."""
    logger.info("starting_api_server", port=8000)
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


def run_collector():
    """Run data collector."""
    logger.info("starting_data_collector")
    asyncio.run(collector_main())


if __name__ == "__main__":
    logger.info("starting_kalshi_services")

    # Start API server in separate process
    api_process = Process(target=run_api, name="api-server")
    api_process.start()

    # Run collector in main process
    try:
        run_collector()
    except KeyboardInterrupt:
        logger.info("shutting_down")
        api_process.terminate()
        api_process.join()
