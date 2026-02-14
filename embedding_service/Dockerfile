FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download models to cache them in the image
# This reduces startup time in production
RUN python3 -c "from sentence_transformers import SentenceTransformer; \
    print('Downloading SapBERT...'); \
    SentenceTransformer('cambridgeltl/SapBERT-from-PubMedBERT-fulltext'); \
    print('Downloading multilingual-e5-large...'); \
    SentenceTransformer('intfloat/multilingual-e5-large'); \
    print('Models cached successfully')"

# Copy application code
COPY app.py .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run with gunicorn for production
# - workers=1: Only one worker needed (models are memory-intensive)
# - threads=4: Handle multiple concurrent requests
# - timeout=60: Allow time for embedding generation
# - preload: Load models before forking workers
CMD exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --threads 4 \
    --timeout 60 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    app:app
