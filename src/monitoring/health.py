"""
Health monitoring system for data collection.
"""
import asyncio
from typing import Dict, Any
from datetime import datetime
from collections import defaultdict
import structlog

from config.settings import settings
from src.database.models import CollectionHealth
from src.database.writer import SupabaseWriter

logger = structlog.get_logger()


class HealthMonitor:
    """Monitors health of data collection components."""

    def __init__(self, db_writer: SupabaseWriter):
        """
        Initialize health monitor.

        Args:
            db_writer: SupabaseWriter instance
        """
        self.db = db_writer

        self.check_interval = settings.health_check_interval_seconds

        # Metrics tracking
        self.metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.is_running = False

        logger.info(
            "health_monitor_initialized",
            interval=self.check_interval
        )

    def record_metric(self, component: str, metric_name: str, value: Any):
        """
        Record a metric for a component.

        Args:
            component: Component name
            metric_name: Metric name
            value: Metric value
        """
        if component not in self.metrics:
            self.metrics[component] = {}

        self.metrics[component][metric_name] = value

        logger.debug(
            "metric_recorded",
            component=component,
            metric=metric_name,
            value=value
        )

    def increment_metric(self, component: str, metric_name: str, amount: int = 1):
        """
        Increment a counter metric.

        Args:
            component: Component name
            metric_name: Metric name
            amount: Amount to increment
        """
        if component not in self.metrics:
            self.metrics[component] = {}

        current = self.metrics[component].get(metric_name, 0)
        self.metrics[component][metric_name] = current + amount

    def get_metrics(self, component: str) -> Dict[str, Any]:
        """
        Get metrics for a component.

        Args:
            component: Component name

        Returns:
            Dictionary of metrics
        """
        return self.metrics.get(component, {})

    def clear_metrics(self, component: str):
        """
        Clear metrics for a component.

        Args:
            component: Component name
        """
        if component in self.metrics:
            self.metrics[component] = {}

    async def check_websocket_health(self) -> Dict[str, Any]:
        """
        Check WebSocket connection health.

        Returns:
            Health metrics
        """
        metrics = self.get_metrics("websocket")

        is_healthy = True
        issues = []

        # Check connection status
        if not metrics.get("is_connected", False):
            is_healthy = False
            issues.append("websocket_disconnected")

        # Check message rate
        messages_per_min = metrics.get("messages_per_minute", 0)
        if messages_per_min < 1:
            is_healthy = False
            issues.append("low_message_rate")

        return {
            "is_connected": metrics.get("is_connected", False),
            "messages_per_minute": messages_per_min,
            "subscribed_markets": metrics.get("subscribed_markets", 0),
            "reconnect_count": metrics.get("reconnect_count", 0),
            "is_healthy": is_healthy,
            "issues": issues
        }

    async def check_rest_poller_health(self) -> Dict[str, Any]:
        """
        Check REST poller health.

        Returns:
            Health metrics
        """
        metrics = self.get_metrics("rest_poller")

        is_healthy = True
        issues = []

        # Check poll success rate
        total_polls = metrics.get("total_polls", 0)
        failed_polls = metrics.get("failed_polls", 0)

        if total_polls > 0:
            success_rate = (total_polls - failed_polls) / total_polls
            if success_rate < 0.8:  # Less than 80% success
                is_healthy = False
                issues.append("low_success_rate")
        else:
            is_healthy = False
            issues.append("no_polls_recorded")

        return {
            "total_polls": total_polls,
            "failed_polls": failed_polls,
            "success_rate": (total_polls - failed_polls) / total_polls if total_polls > 0 else 0,
            "markets_tracked": metrics.get("markets_tracked", 0),
            "is_healthy": is_healthy,
            "issues": issues
        }

    async def check_discovery_health(self) -> Dict[str, Any]:
        """
        Check market discovery health.

        Returns:
            Health metrics
        """
        metrics = self.get_metrics("discovery")

        is_healthy = True
        issues = []

        markets_found = metrics.get("markets_found", 0)
        last_discovery_time = metrics.get("last_discovery_time", 0)

        # Check if discovery is running
        now = int(datetime.utcnow().timestamp())
        time_since_discovery = now - last_discovery_time

        if time_since_discovery > 600:  # More than 10 minutes
            is_healthy = False
            issues.append("stale_discovery")

        if markets_found == 0:
            is_healthy = False
            issues.append("no_markets_found")

        return {
            "markets_found": markets_found,
            "last_discovery_seconds_ago": time_since_discovery,
            "discovery_count": metrics.get("discovery_count", 0),
            "is_healthy": is_healthy,
            "issues": issues
        }

    async def check_database_health(self) -> Dict[str, Any]:
        """
        Check database connection health.

        Returns:
            Health metrics
        """
        metrics = self.get_metrics("database")

        is_healthy = True
        issues = []

        # Check insert success rate
        total_inserts = metrics.get("total_inserts", 0)
        failed_inserts = metrics.get("failed_inserts", 0)

        if total_inserts > 0:
            success_rate = (total_inserts - failed_inserts) / total_inserts
            if success_rate < 0.95:  # Less than 95% success
                is_healthy = False
                issues.append("high_insert_failure_rate")

        # Check queue sizes
        queue_size = metrics.get("queue_size", 0)
        if queue_size > 1000:  # Queue backing up
            is_healthy = False
            issues.append("large_queue_backlog")

        return {
            "total_inserts": total_inserts,
            "failed_inserts": failed_inserts,
            "success_rate": (total_inserts - failed_inserts) / total_inserts if total_inserts > 0 else 1.0,
            "queue_size": queue_size,
            "snapshots_per_minute": metrics.get("snapshots_per_minute", 0),
            "is_healthy": is_healthy,
            "issues": issues
        }

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Complete health status
        """
        websocket_health = await self.check_websocket_health()
        rest_health = await self.check_rest_poller_health()
        discovery_health = await self.check_discovery_health()
        database_health = await self.check_database_health()

        overall_healthy = (
            websocket_health["is_healthy"] and
            rest_health["is_healthy"] and
            discovery_health["is_healthy"] and
            database_health["is_healthy"]
        )

        health_status = {
            "timestamp": int(datetime.utcnow().timestamp()),
            "overall_healthy": overall_healthy,
            "components": {
                "websocket": websocket_health,
                "rest_poller": rest_health,
                "discovery": discovery_health,
                "database": database_health
            }
        }

        logger.info(
            "health_check_completed",
            overall_healthy=overall_healthy,
            websocket=websocket_health["is_healthy"],
            rest=rest_health["is_healthy"],
            discovery=discovery_health["is_healthy"],
            database=database_health["is_healthy"]
        )

        return health_status

    async def save_health_metrics(self):
        """Save health metrics to database."""
        try:
            health_status = await self.perform_health_check()

            for component_name, component_metrics in health_status["components"].items():
                health = CollectionHealth(
                    timestamp=health_status["timestamp"],
                    component=component_name,
                    metrics=component_metrics,
                    is_healthy=component_metrics["is_healthy"]
                )

                await self.db.insert_health_metric(health)

        except Exception as e:
            logger.error("save_health_metrics_failed", error=str(e))

    async def run_continuous_monitoring(self):
        """Run continuous health monitoring."""
        self.is_running = True
        logger.info("health_monitoring_started", interval=self.check_interval)

        while self.is_running:
            try:
                await self.save_health_metrics()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error("monitoring_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def stop(self):
        """Stop health monitoring."""
        self.is_running = False
        logger.info("health_monitor_stopped")
