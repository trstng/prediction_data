"""
Main orchestrator for Kalshi data collection bot.
Coordinates all components and manages lifecycle.
"""
import asyncio
import signal
from typing import Optional
import structlog

from config.settings import settings
from src.utils.logger import setup_logging
from src.database.writer import SupabaseWriter
from src.collectors import (
    LiveStreamCollector,
    RestPoller,
    KalshiAuth,
    KalshiRestClient
)
from src.discovery import MarketFinder
from src.monitoring import HealthMonitor

logger = structlog.get_logger()


class DataCollectorOrchestrator:
    """Orchestrates all data collection components."""

    def __init__(self):
        """Initialize orchestrator and components."""
        # Database
        self.db_writer = SupabaseWriter()

        # Authentication
        self.auth = KalshiAuth()
        self.rest_client = KalshiRestClient(self.auth)

        # Collectors (no historical - that's run separately via standalone script)
        self.live_streamer: Optional[LiveStreamCollector] = None
        self.rest_poller: Optional[RestPoller] = None

        # Discovery
        self.market_finder = MarketFinder(self.db_writer, self.rest_client)

        # Monitoring
        self.health_monitor = HealthMonitor(self.db_writer)

        # Control
        self.is_running = False
        self.tasks = []

        logger.info(
            "orchestrator_initialized",
            target_sports=settings.target_sports_list,
            environment=settings.environment
        )

    async def initialize(self):
        """Initialize all components."""
        logger.info("initializing_components")

        # Login to Kalshi
        success = await self.auth.login()
        if not success:
            raise Exception("Failed to authenticate with Kalshi API")

        # Initialize collectors
        if settings.enable_live_streaming:
            self.live_streamer = LiveStreamCollector(self.db_writer, self.auth)

        if settings.enable_rest_polling:
            self.rest_poller = RestPoller(self.db_writer, self.rest_client)

        logger.info(
            "components_initialized",
            streaming=settings.enable_live_streaming,
            polling=settings.enable_rest_polling
        )

    async def start_market_discovery(self):
        """Start continuous market discovery."""
        logger.info("starting_market_discovery")

        # Initial discovery
        markets = await self.market_finder.discover_all_markets()
        await self.market_finder.save_discovered_markets(markets)

        # Start continuous discovery
        task = asyncio.create_task(self.market_finder.run_continuous_discovery())
        self.tasks.append(task)

        return markets


    async def start_live_streaming(self):
        """Start live WebSocket streaming."""
        if not self.live_streamer:
            logger.info("live_streaming_disabled")
            return

        logger.info("starting_live_streaming")

        # Get active markets
        active_tickers = await self.market_finder.get_active_market_tickers()

        if not active_tickers:
            logger.warning("no_active_markets_for_streaming")
            return

        # Start WebSocket streaming
        task = asyncio.create_task(
            self.live_streamer.run_with_reconnect(active_tickers)
        )
        self.tasks.append(task)

        # Update health metric
        self.health_monitor.record_metric(
            "websocket",
            "subscribed_markets",
            len(active_tickers)
        )

    async def start_rest_polling(self):
        """Start REST API polling."""
        if not self.rest_poller:
            logger.info("rest_polling_disabled")
            return

        logger.info("starting_rest_polling")

        # Get active markets
        active_tickers = await self.market_finder.get_active_market_tickers()

        if not active_tickers:
            logger.warning("no_active_markets_for_polling")
            return

        # Update poller with active markets
        await self.rest_poller.update_active_markets(active_tickers)

        # Start polling
        task = asyncio.create_task(self.rest_poller.run_continuous())
        self.tasks.append(task)

        # Update health metric
        self.health_monitor.record_metric(
            "rest_poller",
            "markets_tracked",
            len(active_tickers)
        )

    async def start_health_monitoring(self):
        """Start health monitoring."""
        logger.info("starting_health_monitoring")

        task = asyncio.create_task(self.health_monitor.run_continuous_monitoring())
        self.tasks.append(task)

    async def refresh_markets_periodically(self):
        """Periodically refresh active markets for collectors."""
        logger.info("starting_periodic_market_refresh")

        while self.is_running:
            try:
                await asyncio.sleep(600)  # Every 10 minutes

                # Get updated market list
                active_tickers = await self.market_finder.get_active_market_tickers()

                logger.info(
                    "refreshing_active_markets",
                    count=len(active_tickers)
                )

                # Update REST poller
                if self.rest_poller:
                    await self.rest_poller.update_active_markets(active_tickers)

                # Update live streamer (would need to implement resubscription)
                # This is a simplified version - in production you'd handle adding/removing markets

                # Update health metrics
                if self.rest_poller:
                    self.health_monitor.record_metric(
                        "rest_poller",
                        "markets_tracked",
                        len(active_tickers)
                    )

            except Exception as e:
                logger.error("market_refresh_error", error=str(e))

    async def run(self):
        """Run the data collector."""
        self.is_running = True

        try:
            # Initialize
            await self.initialize()

            # Start market discovery
            await self.start_market_discovery()

            # Wait for initial markets to be discovered
            await asyncio.sleep(5)

            # Start live data collection (no historical backfill - run explore_historical.py separately)
            await self.start_live_streaming()
            await self.start_rest_polling()

            # Start health monitoring
            await self.start_health_monitoring()

            # Start periodic market refresh
            refresh_task = asyncio.create_task(self.refresh_markets_periodically())
            self.tasks.append(refresh_task)

            logger.info(
                "data_collector_running",
                active_tasks=len(self.tasks)
            )

            # Wait for all tasks
            await asyncio.gather(*self.tasks, return_exceptions=True)

        except Exception as e:
            logger.error("orchestrator_error", error=str(e))
            raise

    async def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("shutting_down")

        self.is_running = False

        # Stop components
        if self.market_finder:
            await self.market_finder.stop()

        if self.rest_poller:
            await self.rest_poller.stop()

        if self.live_streamer:
            await self.live_streamer.close()

        if self.health_monitor:
            await self.health_monitor.stop()

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Flush database queues
        await self.db_writer.flush_all_queues()

        # Close connections
        await self.db_writer.close()
        await self.auth.close()
        await self.rest_client.close()

        logger.info("shutdown_complete")


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging()

    logger.info(
        "kalshi_data_collector_starting",
        version="1.0.0",
        environment=settings.environment
    )

    # Create orchestrator
    orchestrator = DataCollectorOrchestrator()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info("received_shutdown_signal", signal=sig)
        asyncio.create_task(orchestrator.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("fatal_error", error=str(e))
        raise
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
