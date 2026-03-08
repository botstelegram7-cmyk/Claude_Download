# ── PDF Doctor Bot v2.0 — Dockerfile ────────────────────────────────────────
# GitHub: @SerenaXdev
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libtesseract-dev \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    wget \
    fonts-dejavu \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Pre-create fonts dir (fonts downloaded at bot startup via requests) ──────
RUN mkdir -p fonts data

# ── Install Python packages ──────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ──────────────────────────────────────────────────────────────
COPY . .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "main.py"]
