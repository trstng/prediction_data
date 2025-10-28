"""
Configuration settings for Kalshi data collector.
"""
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Kalshi API
    kalshi_api_key: str
    kalshi_api_secret: str
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"

    @property
    def kalshi_api_secret_normalized(self) -> str:
        """Normalize the API secret to handle multi-line private keys."""
        # If it's an RSA key, it should already have proper line breaks
        # Just return as-is since python-dotenv preserves them
        return self.kalshi_api_secret

    # PolyRouter API (optional - only needed for historical backfill via explore_historical.py)
    polyrouter_api_key: str = ""
    polyrouter_base_url: str = "https://api.polyrouter.io/functions/v1"

    # Supabase
    supabase_url: str
    supabase_key: str

    # Data Collection
    target_sports: str = "NFL,NHL,NBA,NCAAF,WEATHER"
    collection_interval_seconds: int = 3
    enable_live_streaming: bool = True
    enable_rest_polling: bool = True

    # Rate Limiting
    polyrouter_requests_per_minute: int = 10
    kalshi_rest_requests_per_minute: int = 100
    batch_insert_size: int = 500

    # Monitoring
    log_level: str = "INFO"
    health_check_interval_seconds: int = 60
    enable_health_monitoring: bool = True

    # WebSocket
    ws_reconnect_delay_seconds: int = 5
    ws_max_reconnect_attempts: int = 10
    ws_ping_interval_seconds: int = 30

    # Deployment
    environment: str = "production"
    port: int = 8000

    @property
    def target_sports_list(self) -> List[str]:
        """Parse target sports into list."""
        return [sport.strip() for sport in self.target_sports.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() in ["development", "dev"]


# Global settings instance
settings = Settings()
