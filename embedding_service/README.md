# Embedding Service

Microservice for generating embeddings using SapBERT and multilingual-e5-large models.

## Features

- **SapBERT** (768-dim): Medical concept embeddings
- **multilingual-e5-large** (1024-dim): Query/passage embeddings
- CPU-based inference (GPU not required)
- REST API with Bearer token authentication
- Docker support for easy deployment

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "sapbert": true,
    "multilingual_e5": true
  }
}
```

### `POST /embed/sapbert`
Generate SapBERT embedding (768-dim).

**Request:**
```json
{
  "text": "diabetes mellitus type 2"
}
```

**Response:**
```json
{
  "embedding": [0.123, -0.456, ...],
  "dim": 768
}
```

### `POST /embed/e5`
Generate multilingual-e5-large embedding (1024-dim).

**Request:**
```json
{
  "text": "query: Does semaglutide reduce weight?"
}
```

**Response:**
```json
{
  "embedding": [0.789, -0.012, ...],
  "dim": 1024
}
```

**Note:** Prefix queries with `"query: "` and passages with `"passage: "` for optimal results.

## Authentication

All embedding endpoints require a Bearer token:

```bash
curl -X POST http://localhost:5000/embed/e5 \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "query: example"}'
```

## Local Development

### 1. Install Dependencies

```bash
cd embedding_service
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
cp .env.example .env
# Edit .env and set EMBEDDING_SERVICE_API_KEY
```

### 3. Run Server

```bash
python3 app.py
```

Server will start on `http://localhost:5000`.

## Docker Deployment

### Build Image

```bash
docker build -t embedding-service .
```

**Note:** First build takes ~10 minutes (downloads models). Models are cached in the image.

### Run Container

```bash
docker run -d \
  --name embedding-service \
  -p 5000:5000 \
  -e EMBEDDING_SERVICE_API_KEY=your-secret-key \
  embedding-service
```

### Test

```bash
# Health check
curl http://localhost:5000/health

# Generate embedding
curl -X POST http://localhost:5000/embed/e5 \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "query: test"}'
```

## Digital Ocean Deployment

### Prerequisites

- Digital Ocean account
- Droplet with 4GB RAM (minimum) or 8GB RAM (recommended)
- Docker installed on Droplet

### Steps

1. **Create Droplet**
   - Image: Ubuntu 22.04 LTS
   - Size: 4GB RAM / 2 vCPU ($24/month) or 8GB RAM / 4 vCPU ($48/month)
   - Add SSH key

2. **SSH to Droplet**
   ```bash
   ssh root@your-droplet-ip
   ```

3. **Install Docker**
   ```bash
   apt update
   apt install -y docker.io docker-compose
   systemctl start docker
   systemctl enable docker
   ```

4. **Transfer Files**
   ```bash
   # On local machine
   scp -r embedding_service root@your-droplet-ip:/root/
   ```

5. **Build and Run**
   ```bash
   # On Droplet
   cd /root/embedding_service
   
   # Generate API key
   export EMBEDDING_SERVICE_API_KEY=$(openssl rand -hex 32)
   echo "API_KEY: $EMBEDDING_SERVICE_API_KEY"  # Save this!
   
   # Build image
   docker build -t embedding-service .
   
   # Run container
   docker run -d \
     --name embedding-service \
     --restart unless-stopped \
     -p 5000:5000 \
     -e EMBEDDING_SERVICE_API_KEY=$EMBEDDING_SERVICE_API_KEY \
     embedding-service
   ```

6. **Configure Firewall**
   ```bash
   ufw allow 22    # SSH
   ufw allow 5000  # Embedding Service
   ufw enable
   ```

7. **Test from External**
   ```bash
   # From your local machine
   curl http://your-droplet-ip:5000/health
   ```

8. **Update Cloud Run Environment**
   ```bash
   # Add to Cloud Run environment variables:
   EMBEDDING_SERVICE_URL=http://your-droplet-ip:5000
   EMBEDDING_SERVICE_API_KEY=<key-from-step-5>
   ```

## Resource Requirements

- **Memory**: 4GB minimum, 8GB recommended
- **CPU**: 2 vCPU minimum
- **Storage**: 10GB (includes models)
- **Inference Time**: 100-300ms per query (CPU)

## Monitoring

### Check Logs

```bash
docker logs -f embedding-service
```

### Check Resource Usage

```bash
docker stats embedding-service
```

## Troubleshooting

### Models Not Loading

If models fail to load, check available memory:
```bash
free -h
```

Ensure at least 4GB RAM is available.

### Connection Refused

Check if service is running:
```bash
docker ps | grep embedding-service
curl http://localhost:5000/health
```

### Slow Response

CPU inference takes 100-300ms per request. This is normal. GPU is not required.

## Production Checklist

- [ ] Set strong `EMBEDDING_SERVICE_API_KEY`
- [ ] Configure firewall (only allow Cloud Run IP if possible)
- [ ] Set up monitoring/alerting
- [ ] Configure automatic backups
- [ ] Test failover scenarios
- [ ] Document API key in secure location

## License

Same as parent project.
