#!/bin/bash
# Startup script that runs both the data collector and health check API

# Start the health check API in the background
python -m uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000} &

# Store the PID
API_PID=$!

# Start the main data collector
python -m src.main &

# Store the PID
COLLECTOR_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down..."
    kill $API_PID
    kill $COLLECTOR_PID
    wait $API_PID
    wait $COLLECTOR_PID
    exit 0
}

# Trap SIGTERM and SIGINT
trap shutdown SIGTERM SIGINT

# Wait for both processes
wait $API_PID
wait $COLLECTOR_PID
