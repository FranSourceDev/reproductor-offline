FROM python:3.12-slim

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY media_player/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from media_player subdirectory
COPY media_player/ .

# Create downloads directory
RUN mkdir -p static/downloads

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests, sys; r = requests.get('http://localhost:8000/health'); sys.exit(0 if r.status_code == 200 else 1)"

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
