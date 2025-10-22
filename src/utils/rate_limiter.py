"""
Rate limiting utilities.
"""
import asyncio
import time
from typing import Optional
import structlog

logger = structlog.get_logger()


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_minute: int, name: str = "rate_limiter"):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            name: Name for logging purposes
        """
        self.requests_per_minute = requests_per_minute
        self.name = name
        self.tokens = requests_per_minute
        self.updated_at = time.monotonic()
        self.lock = asyncio.Lock()

        # Calculate token refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0

        logger.info(
            f"{name}_initialized",
            requests_per_minute=requests_per_minute,
            refill_rate=self.refill_rate
        )

    async def acquire(self, tokens: int = 1):
        """
        Acquire tokens from the bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default 1)
        """
        async with self.lock:
            while True:
                now = time.monotonic()
                time_passed = now - self.updated_at
                self.updated_at = now

                # Refill tokens based on time passed
                self.tokens = min(
                    self.requests_per_minute,
                    self.tokens + time_passed * self.refill_rate
                )

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    logger.debug(
                        f"{self.name}_tokens_acquired",
                        tokens=tokens,
                        remaining=self.tokens
                    )
                    return

                # Calculate wait time to get enough tokens
                wait_time = (tokens - self.tokens) / self.refill_rate
                logger.debug(
                    f"{self.name}_rate_limit_wait",
                    wait_seconds=wait_time,
                    tokens_needed=tokens
                )
                await asyncio.sleep(wait_time)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self.lock:
            now = time.monotonic()
            time_passed = now - self.updated_at
            self.updated_at = now

            # Refill tokens
            self.tokens = min(
                self.requests_per_minute,
                self.tokens + time_passed * self.refill_rate
            )

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts to 429 responses."""

    def __init__(self, requests_per_minute: int, name: str = "adaptive_limiter"):
        super().__init__(requests_per_minute, name)
        self.base_rpm = requests_per_minute
        self.backoff_factor = 1.0

    async def report_rate_limit_hit(self):
        """Report that a 429 was received - reduce request rate."""
        async with self.lock:
            self.backoff_factor *= 0.7  # Reduce to 70%
            self.backoff_factor = max(0.1, self.backoff_factor)  # Min 10%
            new_rpm = int(self.base_rpm * self.backoff_factor)

            logger.warning(
                f"{self.name}_rate_limit_hit",
                old_rpm=self.requests_per_minute,
                new_rpm=new_rpm,
                backoff_factor=self.backoff_factor
            )

            self.requests_per_minute = new_rpm
            self.refill_rate = new_rpm / 60.0

    async def report_success(self):
        """Report successful request - slowly increase rate."""
        async with self.lock:
            # Slowly increase back to normal
            self.backoff_factor = min(1.0, self.backoff_factor * 1.01)
            new_rpm = int(self.base_rpm * self.backoff_factor)

            if new_rpm != self.requests_per_minute:
                self.requests_per_minute = new_rpm
                self.refill_rate = new_rpm / 60.0
