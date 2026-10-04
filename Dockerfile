# =================================================================
# Dockerfile for Personal AI Accountability Coach
# =================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies (curl for healthchecks, tzdata for timezone)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and configuration files
COPY src/ /app/src/
COPY config.yaml /app/
COPY .env.example /app/

# Ensure persistent data directory exists
RUN mkdir -p /app/data

# Run application as unprivileged user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/data"]

CMD ["python", "src/main.py"]
