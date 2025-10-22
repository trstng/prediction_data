"""
Simple FastAPI health check endpoint for Railway.
"""
from fastapi import FastAPI
from datetime import datetime
import structlog

from config.settings import settings

logger = structlog.get_logger()

app = FastAPI(title="Kalshi Data Collector", version="1.0.0")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "kalshi-data-collector",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "target_sports": settings.target_sports_list
    }


@app.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"ping": "pong"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
