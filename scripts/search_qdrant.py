#!/usr/bin/env python3
"""
Qdrant search with real embeddings (Fixed for Filtering)
Uses scroll() + manual vector similarity to work with available API
"""

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import sys
import time
import argparse
import logging
import re
import requests

# Initialize Qdrant client
print("Initializing Qdrant client...")
client = QdrantClient(path="./qdrant_medical_db")
print("✓ Qdrant client initialized")

# Load models
print("Loading embedding models...")

try:
    sapbert = SentenceTransformer('cambridgeltl/SapBERT-from-PubMedBERT-fulltext')
    print("✓ SapBERT loaded")
except Exception as e:
    print(f"✗ Error loading SapBERT: {e}")
    # テスト用にダミーモデルで続行する場合のフォールバックが必要ならここに記述
    raise

try:
    multilingual_e5 = SentenceTransformer('intfloat/multilingual-e5-large')
    print("✓ multilingual-e5 loaded")
except Exception as e:
    print(f"✗ Error loading multilingual-e5: {e}")
    raise

print("✓ All models loaded\n")


def translate_query(query):
    """Translate Japanese query to English using MedGemma via Ollama."""
    if not re.search(r'[\u3040-\u30FF\u4E00-\u9FFF]', query):
        return query
    prompt = f"""Task: Translate this Japanese medical question to English.
Rules: Output ONLY the English translation text. No explanations.

Japanese: {query}
English:"""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'medgemma',
                'prompt': prompt,
                'stream': False,
                'options': {'num_predict': 128, 'temperature': 0.0}
            },
            timeout=30
        )
        text = response.json().get('response', '').strip()
        if '\n' in text:
            text = text.split('\n')[0]
        return text if text else query
    except Exception:
        return query


def setup_logging(log_file=None):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    formatter = logging.Formatter('%(message)s')
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def extract_keywords(query):
    """Extract important keywords from English query for reranking"""
    medical_keywords = [
        'osteoarthritis', 'knee', 'hip', 'joint', 'arthritis',
        'glp1', 'glp-1', 'glucagon', 'agonist', 'semaglutide',
        'liraglutide', 'tirzepatide', 'metformin',
        'diabetes', 'obesity', 'weight', 'loss',
        'cardiovascular', 'heart', 'stroke', 'mi',
        'efficacy', 'safety', 'treatment', 'therapy',
        'effectiveness', 'clinical', 'trial',
        'randomized', 'controlled', 'double-blind', 'placebo',
        'parkinson', 'alzheimer', 'dementia', 'liver', 'nash'
    ]
    
    query_lower = query.lower()
    extracted = []
    
    for keyword in medical_keywords:
        if keyword in query_lower:
            extracted.append(keyword)
    
    words = query_lower.split()
    for word in words:
        word = word.strip('.,!?;:"\'-()[]{}')
        if len(word) >= 4 and word not in extracted:
            if any(med in word for med in ['osteo', 'arthr', 'cardio', 'diabet', 'obes']):
                extracted.append(word)
    
    return list(set(extracted))


def calculate_keyword_bonus(paper, keywords):
    """Calculate bonus score based on keyword matching"""
    if not keywords:
        return 0.0
    
    high_importance = ['osteoarthritis', 'knee', 'hip', 'joint', 'arthritis',
                       'parkinson', 'alzheimer', 'dementia', 'liver', 'nash']
    
    medium_importance = ['cardiovascular', 'heart', 'stroke', 'diabetes', 
                         'obesity', 'weight', 'metabolic']
    
    low_importance = ['glp1', 'glp-1', 'glucagon', 'agonist', 'semaglutide',
                      'liraglutide', 'tirzepatide', 'treatment', 'therapy',
                      'efficacy', 'safety', 'clinical', 'trial']
    
    title = paper.get('metadata', {}).get('title', '').lower()
    pico = paper.get('pico_en', {})
    patient = pico.get('patient', '').lower()
    intervention = pico.get('intervention', '').lower()
    outcome = pico.get('outcome', '').lower()
    
    all_text = f"{title} {patient} {intervention} {outcome}"
    
    bonus = 0.0
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in all_text:
            if keyword in high_importance:
                bonus += 0.05
            elif keyword in medium_importance:
                bonus += 0.03
            else:
                bonus += 0.01
    
    return min(bonus, 0.15)


def search_by_vector_similarity(query_vec, collection_name, limit=10, query=None):
    """Search by manual vector similarity with 2-stage reranking"""
    logger = logging.getLogger()
    logger.info(f"  Fetching all points from {collection_name}...")
    
    try:
        # Fetch all points from Qdrant
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=True
        )
        
        all_points = scroll_result[0]
        logger.info(f"  ✓ Fetched {len(all_points)} points from {collection_name}")
        
        if not all_points:
            return []
        
        # Extract vectors and payloads based on available vectors
        if all_points[0].vector and isinstance(all_points[0].vector, dict):
            if 'e5_pico' in all_points[0].vector:
                vectors = np.array([point.vector['e5_pico'] for point in all_points])
                vector_name = "e5_pico"
            elif 'e5_questions_en' in all_points[0].vector:
                vectors = np.array([point.vector['e5_questions_en'] for point in all_points])
                vector_name = "e5_questions_en"
            else:
                vectors = np.array([point.vector['sapbert_pico'] for point in all_points])
                vector_name = "sapbert_pico"
        else:
            # Handle case where vector might not be a dict (backward compatibility)
            vectors = np.array([point.vector for point in all_points])
            vector_name = "default"
        
        logger.info(f"  Using {vector_name} vectors ({vectors.shape[1]}-dim)")
        
        # Stage 1: Calculate cosine similarity
        similarities = cosine_similarity([query_vec], vectors)[0]
        
        # Stage 2: Keyword-based reranking
        if query:
            keywords = extract_keywords(query)
            
            if keywords:
                logger.info(f"  Keywords extracted: {keywords}")
                
                candidate_count = min(50, len(all_points))
                top_indices = np.argsort(similarities)[::-1][:candidate_count]
                
                reranked_results = []
                for idx in top_indices:
                    point = all_points[idx]
                    base_score = similarities[idx]
                    
                    paper = {
                        'json_path': point.payload.get('json_path', ''),
                        'paper_id': point.payload.get('paper_id', ''),
                        'score': float(base_score),
                        'pico_en': point.payload.get('pico_en', {}),
                        'metadata': point.payload.get('metadata', {})
                    }
                    
                    bonus = calculate_keyword_bonus(paper, keywords)
                    final_score = base_score + bonus
                    
                    paper['score'] = float(final_score)
                    paper['base_score'] = float(base_score)
                    paper['bonus'] = float(bonus)
                    
                    reranked_results.append(paper)
                
                reranked_results.sort(key=lambda x: x['score'], reverse=True)
                return reranked_results[:limit]
        
        # Fallback: Simple vector similarity
        top_indices = np.argsort(similarities)[::-1][:limit]
        
        results = []
        for idx in top_indices:
            point = all_points[idx]
            score = similarities[idx]
            
            results.append({
                'json_path': point.payload.get('json_path', ''),
                'paper_id': point.payload.get('paper_id', ''),
                'score': float(score),
                'pico_en': point.payload.get('pico_en', {}),
                'metadata': point.payload.get('metadata', {})
            })
        
        return results
        
    except Exception as e:
        logger.info(f"  ✗ Error in search_by_vector_similarity: {e}")
        return []


def search_medical_papers(query, top_k=10):
    """Multi-stage medical paper search"""
    logger = logging.getLogger()
    start_time = time.time()

    logger.info("="*70)
    logger.info("Medical Paper Search")
    logger.info("="*70)

    # Translate Japanese query to English before search
    search_query = translate_query(query)
    if search_query != query:
        logger.info(f"Translated: {search_query}")

    lang = 'ja' if search_query != query else 'en'

    # Generate query embedding using translated (English) query
    query_vec = multilingual_e5.encode(f"query: {search_query}", normalize_embeddings=True)
    query_vec = np.array(query_vec)

    # Search — pass translated query so extract_keywords() sees English terms
    papers = search_by_vector_similarity(
        query_vec,
        "medical_papers",
        limit=top_k,
        query=search_query
    )

    elapsed_time = (time.time() - start_time) * 1000

    return {
        'query': query,
        'search_query': search_query,
        'query_language': lang,
        'papers': papers,
        'search_strategy': 'vector_similarity',
        'search_time_ms': elapsed_time
    }


def search_atomic_facts(query, limit=5, paper_ids=None):
    """
    Search atomic facts collection by vector similarity
    CRITICAL FIX: Strictly filters by paper_ids if provided to avoid noise.
    """
    logger = logging.getLogger()
    logger.info(f"Searching atomic_facts...")
    
    # Generate Query Vector
    query_vec = sapbert.encode(query, normalize_embeddings=True)
    query_vec = np.array(query_vec)
    
    try:
        # Fetch atomic facts
        scroll_result = client.scroll(
            collection_name="atomic_facts",
            limit=2000, # Increased limit to ensure we find facts for specific papers
            with_payload=True,
            with_vectors=True
        )
        
        all_facts = scroll_result[0]
        logger.info(f"  ✓ Fetched {len(all_facts)} atomic facts total")
        
        if not all_facts:
            return []
        
        # --- FILTERING LOGIC ---
        if paper_ids:
            # Normalize paper_ids to strings for comparison
            target_ids = set(str(pid) for pid in paper_ids)
            logger.info(f"  ⚠ Filtering for papers: {target_ids}")
            
            filtered_facts = []
            for f in all_facts:
                fact_pid = str(f.payload.get('paper_id', ''))
                if fact_pid in target_ids:
                    filtered_facts.append(f)
            
            all_facts = filtered_facts
            logger.info(f"  ✓ Filtered down to {len(all_facts)} facts belonging to target papers")
            
            # If no facts found for these papers, return empty list (better than returning noise)
            if not all_facts:
                logger.info("  ! No atomic facts found for the retrieved papers.")
                return []
        # -----------------------

        # Extract vectors
        if isinstance(all_facts[0].vector, dict):
            vectors = np.array([fact.vector['sapbert_fact'] for fact in all_facts])
        else:
            vectors = np.array([fact.vector for fact in all_facts])
            
        # Calculate similarity
        similarities = cosine_similarity([query_vec], vectors)[0]
        
        # Sort
        top_indices = np.argsort(similarities)[::-1][:limit]
        
        results = []
        for idx in top_indices:
            fact = all_facts[idx]
            score = similarities[idx]
            
            results.append({
                'json_path': fact.payload.get('json_path', ''),
                'paper_id': fact.payload.get('paper_id', ''),
                'fact_text': fact.payload.get('fact_text', ''),
                'score': float(score)
            })
        
        return results
        
    except Exception as e:
        logger.info(f"  ✗ Error in search_atomic_facts: {e}")
        return []

if __name__ == '__main__':
    # CLI interface with argument parsing
    parser = argparse.ArgumentParser(description='Search medical papers using Qdrant')
    parser.add_argument('query', help='Search query text')
    parser.add_argument('--top_k', type=int, default=5, help='Number of results to return (default: 5)')
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Execute search
    results = search_medical_papers(args.query, top_k=args.top_k)
    papers = results.get('papers', [])
    query_lang = results.get('query_language', 'en')
    search_time = results.get('search_time_ms', 0)
    
    # Display results
    print(f"\n検索クエリ: {results['query']}")
    print(f"言語: {'日本語' if query_lang == 'ja' else '英語'}")
    print(f"検索時間: {search_time:.2f}ms")
    print(f"\n上位{len(papers)}件の関連論文:")
    print("=" * 80)
    
    for i, paper in enumerate(papers, 1):
        title = paper.get('metadata', {}).get('title', 'N/A')
        pmid = paper.get('paper_id', 'N/A')
        journal = paper.get('metadata', {}).get('journal', 'N/A')
        year = paper.get('metadata', {}).get('publication_year', 'N/A')
        score = round(float(paper.get('score', 0)), 3)
        
        print(f"\n{i}. {title}")
        print(f"   PMID: {pmid}")
        print(f"   スコア: {score}")
        print(f"   ジャーナル: {journal}")
        if year and year != 'N/A':
            print(f"   年: {year}")
    
    if len(papers) == 0:
        print("\n関連する論文が見つかりませんでした。")
    
    print("\n" + "=" * 80)
