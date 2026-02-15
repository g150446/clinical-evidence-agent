FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal set for Cloud Run)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ ./templates/
COPY scripts/ ./scripts/

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Start command
# Note: No embedding models are loaded - uses Embedding Service API
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 600 app:app

