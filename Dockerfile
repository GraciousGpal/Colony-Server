# Colony-Server Dockerfile
# Python 3.13 game server with TCP server, SQLite database, and Discord bot integration

FROM python:3.13-slim AS base

# Metadata labels
LABEL maintainer="Colony-Server"
LABEL description="Colony game server - Python 3.13 TCP server with SQLite and Discord integration"
LABEL version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and tini for proper init system
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tini \
    tshark \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash colony

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY --chown=colony:colony requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=colony:colony . .

# Create data directory for database persistence
RUN mkdir -p /app/data && \
    chown -R colony:colony /app/data

# Switch to non-root user
USER colony

# Expose TCP server port
EXPOSE 25565

# Define volume for database persistence
VOLUME ["/app/data"]

# Health check for TCP server port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(5); s.connect(('localhost', 25565)); s.close()" || exit 1

# Use tini as init system for proper signal handling with multiprocessing
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the launcher
CMD ["python", "launcher.py"]