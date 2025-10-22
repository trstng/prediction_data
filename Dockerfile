# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 collector && \
    chown -R collector:collector /app

# Switch to non-root user
USER collector

# Expose port for health checks
EXPOSE 8000

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "-m", "src.main"]
