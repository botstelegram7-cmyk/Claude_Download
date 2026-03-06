# ──────────────────────────────────────────────────────
# Serena Downloader Bot — Dockerfile
# ──────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies + FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create runtime directories
RUN mkdir -p /tmp/serena_db /tmp/serena_dl

# Expose port for health check
EXPOSE 8080

# Start bot
CMD ["python", "bot.py"]
