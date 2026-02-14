#!/usr/bin/env python3
"""
Embedding Service - Microservice for SapBERT and multilingual-e5-large
Runs on Digital Ocean, provides REST API for embedding generation
"""

from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import logging
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load API key from environment
API_KEY = os.getenv('EMBEDDING_SERVICE_API_KEY')
if not API_KEY:
    logger.warning("EMBEDDING_SERVICE_API_KEY not set - API will be unprotected!")

# Global model variables (loaded on startup)
sapbert = None
multilingual_e5 = None


def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not API_KEY:
            # If no API key is configured, allow all requests
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Missing Authorization header'}), 401
        
        # Expected format: "Bearer <api_key>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'error': 'Invalid Authorization header format'}), 401
        
        if parts[1] != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


def load_models():
    """Load embedding models on startup"""
    global sapbert, multilingual_e5
    
    logger.info("Loading embedding models...")
    
    try:
        logger.info("Loading SapBERT...")
        sapbert = SentenceTransformer(
            'cambridgeltl/SapBERT-from-PubMedBERT-fulltext',
            device='cpu'
        )
        logger.info("✓ SapBERT loaded (768-dim)")
    except Exception as e:
        logger.error(f"Failed to load SapBERT: {e}")
        raise
    
    try:
        logger.info("Loading multilingual-e5-large...")
        multilingual_e5 = SentenceTransformer(
            'intfloat/multilingual-e5-large',
            device='cpu'
        )
        logger.info("✓ multilingual-e5-large loaded (1024-dim)")
    except Exception as e:
        logger.error(f"Failed to load multilingual-e5: {e}")
        raise
    
    logger.info("✓ All models loaded successfully")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'models_loaded': {
            'sapbert': sapbert is not None,
            'multilingual_e5': multilingual_e5 is not None
        }
    })


@app.route('/embed/sapbert', methods=['POST'])
@require_api_key
def embed_sapbert():
    """
    Generate SapBERT embedding (768-dim)
    
    Request body:
        {"text": "medical concept or fact"}
    
    Response:
        {"embedding": [768-dim array], "dim": 768}
    """
    if sapbert is None:
        return jsonify({'error': 'SapBERT model not loaded'}), 503
    
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field in request body'}), 400
    
    text = data['text']
    if not text or not text.strip():
        return jsonify({'error': 'Text cannot be empty'}), 400
    
    try:
        # Generate embedding
        embedding = sapbert.encode(
            text.strip(),
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        # Convert to list for JSON serialization
        embedding_list = embedding.tolist()
        
        logger.info(f"SapBERT embedding generated (text length: {len(text)})")
        
        return jsonify({
            'embedding': embedding_list,
            'dim': len(embedding_list)
        })
    
    except Exception as e:
        logger.error(f"Error generating SapBERT embedding: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/embed/e5', methods=['POST'])
@require_api_key
def embed_e5():
    """
    Generate multilingual-e5-large embedding (1024-dim)
    
    Request body:
        {"text": "query: medical question"}
        
    Note: For queries, prefix with "query: "
          For passages, prefix with "passage: "
    
    Response:
        {"embedding": [1024-dim array], "dim": 1024}
    """
    if multilingual_e5 is None:
        return jsonify({'error': 'multilingual-e5 model not loaded'}), 503
    
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field in request body'}), 400
    
    text = data['text']
    if not text or not text.strip():
        return jsonify({'error': 'Text cannot be empty'}), 400
    
    try:
        # Generate embedding
        embedding = multilingual_e5.encode(
            text.strip(),
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        # Convert to list for JSON serialization
        embedding_list = embedding.tolist()
        
        logger.info(f"E5 embedding generated (text length: {len(text)})")
        
        return jsonify({
            'embedding': embedding_list,
            'dim': len(embedding_list)
        })
    
    except Exception as e:
        logger.error(f"Error generating E5 embedding: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API information"""
    return jsonify({
        'service': 'Clinical Evidence Agent - Embedding Service',
        'version': '1.0.0',
        'endpoints': {
            '/health': 'GET - Health check',
            '/embed/sapbert': 'POST - Generate SapBERT embedding (768-dim)',
            '/embed/e5': 'POST - Generate E5 embedding (1024-dim)'
        },
        'authentication': 'Bearer token in Authorization header' if API_KEY else 'None (unprotected)',
        'models': {
            'sapbert': 'cambridgeltl/SapBERT-from-PubMedBERT-fulltext',
            'e5': 'intfloat/multilingual-e5-large'
        }
    })


if __name__ == '__main__':
    # Load models before starting server
    load_models()
    
    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"Starting Embedding Service on port {port}...")
    
    # Run server
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
