#!/usr/bin/env python3
"""
Generate embeddings for all obesity treatment papers
Merged version with:
- Fixed UUID generation (from generate_embeddings_fixed.py)
- Deduplication logic (from generate_embeddings.py)
- Qdrant path: ./qdrant_medical_db
- Stops on error
- Support for Qdrant Cloud (--cloud flag)
"""

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json
import numpy as np
import time
import uuid
import logging
import subprocess
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress sentence-transformers INFO/DEBUG logs
logging.getLogger('sentence_transformers').setLevel(logging.ERROR)

def get_cache_size(model_path):
    """Get cache size in MB for a given HuggingFace model path"""
    try:
        result = subprocess.run(
            ['du', '-sh', model_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except:
        pass
    return "Unknown"

def initialize_qdrant_client(use_cloud=False):
    """Initialize Qdrant client - local or cloud"""
    if use_cloud:
        # Get cloud credentials from environment
        cloud_url = os.getenv('QDRANT_CLOUD_ENDPOINT')
        cloud_api_key = os.getenv('QDRANT_CLOUD_API_KEY')
        
        if not cloud_url or not cloud_api_key:
            print("✗ Error: QDRANT_CLOUD_ENDPOINT or QDRANT_CLOUD_API_KEY not found in .env")
            print("Please ensure these variables are set in your .env file:")
            print("  QDRANT_CLOUD_ENDPOINT=https://your-cluster.cloud.qdrant.io")
            print("  QDRANT_CLOUD_API_KEY=your-api-key")
            sys.exit(1)
        
        print("Connecting to Qdrant Cloud...")
        print(f"  Endpoint: {cloud_url}")
        client = QdrantClient(url=cloud_url, api_key=cloud_api_key)
        print("✓ Connected to Qdrant Cloud")
        return client, "cloud"
    else:
        # Local mode
        print("Initializing local Qdrant client...")
        client = QdrantClient(path="./qdrant_medical_db")
        print("✓ Local Qdrant client initialized")
        return client, "local"


def setup_collections(client):
    """Create Qdrant collections if they don't exist"""
    print("\nChecking collections...")
    
    # Check if medical_papers collection exists
    try:
        client.get_collection("medical_papers")
        print("✓ Collection 'medical_papers' exists")
    except Exception:
        print("  Creating collection: medical_papers...")
        client.create_collection(
            collection_name="medical_papers",
            vectors_config={
                "sapbert_pico": VectorParams(size=768, distance=Distance.COSINE),
                "e5_pico": VectorParams(size=1024, distance=Distance.COSINE),
                "e5_questions_en": VectorParams(size=1024, distance=Distance.COSINE)
            }
        )
        print("  ✓ Created collection: medical_papers")
    
    # Check if atomic_facts collection exists
    try:
        client.get_collection("atomic_facts")
        print("✓ Collection 'atomic_facts' exists")
    except Exception:
        print("  Creating collection: atomic_facts...")
        client.create_collection(
            collection_name="atomic_facts",
            vectors_config={
                "sapbert_fact": VectorParams(size=768, distance=Distance.COSINE)
            }
        )
        print("  ✓ Created collection: atomic_facts")

# Load models (use default HuggingFace cache)
print("\nLoading embedding models...")
print("(Models are cached in ~/.cache/huggingface)")

# Load SapBERT
sapbert_cache = Path.home() / '.cache/huggingface/hub/models--cambridgeltl--SapBERT-from-PubMedBERT-fulltext'
if sapbert_cache.exists():
    size = get_cache_size(sapbert_cache)
    print(f"Loading SapBERT from cache ({size})...")
else:
    print("Loading SapBERT (first run - will download ~420MB)...")

try:
    sapbert = SentenceTransformer(
        'cambridgeltl/SapBERT-from-PubMedBERT-fulltext'
    )
    print("✓ SapBERT loaded")
except Exception as e:
    print(f"✗ Error loading SapBERT: {e}")
    raise

# Load multilingual-e5
e5_cache = Path.home() / '.cache/huggingface/hub/models--intfloat--multilingual-e5-large'
if e5_cache.exists():
    size = get_cache_size(e5_cache)
    print(f"Loading multilingual-e5 from cache ({size})...")
else:
    print("Loading multilingual-e5 (first run - will download ~2.4GB)...")

try:
    multilingual_e5 = SentenceTransformer(
        'intfloat/multilingual-e5-large'
    )
    print("✓ multilingual-e5 loaded")
except Exception as e:
    print(f"✗ Error loading multilingual-e5: {e}")
    raise

print("✓ All models loaded\n")


def process_paper(paper_path):
    """Process single paper and generate embeddings
    
    Returns:
        success: bool
        paper_id: str
        paper_uuid: str (UUID for Qdrant)
        points_count: int (main collection + atomic facts)
    """
    
    try:
        # Load structured data
        with open(paper_path, 'r', encoding='utf-8') as f:
            paper = json.load(f)
        
        # Extract data
        paper_id = paper.get('paper_id', '')
        pico = paper['language_independent_core'].get('pico_en', {})
        atomic_facts = paper['language_independent_core'].get('atomic_facts_en', [])
        metadata = paper.get('metadata', {})
        
        # Check for generated questions
        if 'multilingual_interface' not in paper:
            print(f"  ! Missing multilingual_interface in {paper_id}")
            return False, None, None, 0
        
        generated_questions = paper['multilingual_interface'].get('generated_questions', {})
        if isinstance(generated_questions, list):
            questions_en = generated_questions          # flat list — already English strings
        elif isinstance(generated_questions, dict):
            questions_en = generated_questions.get('en', [])
        else:
            questions_en = []
        
        # 1. SapBERT PICO embedding (768 dim)
        pico_combined = f"{pico.get('patient', '')} {pico.get('intervention', '')} {pico.get('comparison', '')} {pico.get('outcome', '')}"
        sapbert_pico_vec = sapbert.encode(pico_combined, normalize_embeddings=True)
        
        # 2. E5 PICO embedding (1024 dim, with passage: prefix)
        e5_pico_vec = multilingual_e5.encode(
            f"passage: {pico_combined}", 
            normalize_embeddings=True
        )
        
        # 3. E5 English questions (1024 dim, average with query: prefix)
        if questions_en:
            e5_q_en_vecs = [
                multilingual_e5.encode(f"query: {q}", normalize_embeddings=True)
                for q in questions_en
            ]
            e5_questions_en_vec = np.mean(e5_q_en_vecs, axis=0)
        else:
            e5_questions_en_vec = np.zeros(1024, dtype=np.float32)
        

        # Deterministic UUID from paper_id: re-runs update the same point, no duplicates
        paper_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, paper_id))
        
        # 5. Upsert to medical_papers collection (3 named vectors)
        client.upsert(
            collection_name="medical_papers",
            points=[
                PointStruct(
                    id=paper_uuid,
                    vector={
                        "sapbert_pico": sapbert_pico_vec.tolist(),
                        "e5_pico": e5_pico_vec.tolist(),
                        "e5_questions_en": e5_questions_en_vec.tolist()
                    },
                    payload={
                        "json_path": str(paper_path),
                        "paper_id": paper_id,
                        "pico_en": pico,
                        "metadata": metadata,
                        "mesh_terms": metadata.get('mesh_terms', [])
                    }
                )
            ]
        )
        
        # 6. Atomic facts (separate collection, 1 named vector per fact)
        atomic_points = []
        for idx, fact in enumerate(atomic_facts):
            fact_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{paper_id}_fact_{idx}"))
            fact_vec = sapbert.encode(fact, normalize_embeddings=True)
            atomic_points.append(
                PointStruct(
                    id=fact_uuid,
                    vector={"sapbert_fact": fact_vec.tolist()},
                    payload={
                        "json_path": str(paper_path),
                        "paper_id": paper_id,
                        "fact_text": fact,
                        "fact_index": idx
                    }
                )
            )
        
        client.upsert(
            collection_name="atomic_facts",
            points=atomic_points
        )
        
        return True, paper_id, paper_uuid, 1 + len(atomic_points)
        
    except Exception as e:
        print(f"  ✗ Error processing {paper_path.name}: {e}")
        return False, paper_path.stem, None, 0


def main():
    """Process all structured papers"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate embeddings for medical papers')
    parser.add_argument('--cloud', action='store_true', 
                        help='Use Qdrant Cloud instead of local database')
    parser.add_argument('--check', action='store_true',
                        help='Only check existing embeddings, do not generate new ones')
    args = parser.parse_args()
    
    print("="*70)
    print("Qdrant Embedding Generation (Merged Version)")
    print("="*70)
    
    # Initialize Qdrant client
    global client
    client, mode = initialize_qdrant_client(use_cloud=args.cloud)
    
    print(f"\nMode: {'Qdrant Cloud' if mode == 'cloud' else 'Local'}")
    
    # Setup collections (create if they don't exist)
    setup_collections(client)
    
    # Check which papers actually have embeddings in Qdrant
    print("\nChecking Qdrant for existing embeddings...\n")
    
    try:
        # Get existing papers in Qdrant
        medical_info = client.get_collection("medical_papers")
        
        # Get all existing PMIDs
        existing_pmids = set()
        scroll_result = client.scroll(
            collection_name="medical_papers",
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        
        for point in scroll_result[0]:
            pmid = point.payload.get('paper_id', '')
            if pmid:
                existing_pmids.add(pmid)
        
        print(f"Existing papers in Qdrant: {len(existing_pmids)}")
        
    except Exception as e:
        print(f"✗ Error checking Qdrant: {e}")
        existing_pmids = set()
    
    # If --check flag is set, only check and exit
    if args.check:
        print(f"\n{'='*70}")
        print("Check Mode - Exiting without generating embeddings")
        print(f"{'='*70}")
        print(f"Existing papers in database: {len(existing_pmids)}")
        return
    
    # Find all structured papers across all 3 domains and subsections
    all_papers = []
    
    SUBSECTIONS = {
        'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
        'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
        'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
    }
    
    for domain in ['pharmacologic', 'surgical', 'lifestyle']:
        domain_papers = 0
        
        for subsection in SUBSECTIONS[domain]:
            papers_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
            
            if not papers_dir.exists():
                print(f"  Subsection {subsection}: No papers directory found")
                continue
            
            paper_files = sorted(papers_dir.glob('PMID_*.json'))
            all_papers.extend(((domain, subsection), pf) for pf in paper_files)
            domain_papers += len(paper_files)
        
        print(f"Domain {domain}: {domain_papers} papers found")
    
    total_papers = len(all_papers)
    print(f"\nTotal papers to process: {total_papers}")
    
    # Determine which papers need to be processed
    papers_to_process = [((domain, subsection), pf) for (domain, subsection), pf in all_papers if pf.stem.replace('PMID_', '') not in existing_pmids]
    
    print(f"Papers to process: {len(papers_to_process)}")
    print(f"Already have embeddings: {len(existing_pmids)}\n")
    
    if len(papers_to_process) == 0:
        print("All papers already have embeddings in Qdrant!")
        print("No processing needed.")
        return
    
    # Process all papers that don't have embeddings
    print(f"Processing {len(papers_to_process)} papers...\n")
    
    # Process all papers
    total_main_points = 0
    total_atomic_points = 0
    success_count = 0
    error_count = 0
    
    start_time = time.time()
    
    for idx, ((domain, subsection), paper_file) in enumerate(papers_to_process, 1):
        paper_id = paper_file.stem.replace('PMID_', '')
        
        print(f"[{idx}/{len(papers_to_process)}] {domain}/{subsection}/{paper_file.name} - Generating embeddings...")
        
        success, paper_id, paper_uuid, points = process_paper(paper_file)
        
        if success:
            success_count += 1
            total_main_points += 1
            total_atomic_points += points
            
            if idx % 10 == 0 or idx == len(papers_to_process):
                elapsed = time.time() - start_time
                progress = (idx / len(papers_to_process)) * 100
                print(f"  Progress: {progress:.1f}% | Success: {success_count} | Time: {elapsed:.1f}s | Main: {total_main_points} | Atomic: {total_atomic_points}")
        else:
            error_count += 1
            print(f"  ✗ Failed to generate embeddings for {paper_id}")
            
            # Stop on error
            print(f"\n✗ Error detected. Stopping processing.")
            break
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Qdrant Embedding Generation Complete")
    print(f"{'='*70}")
    print(f"\nSummary:")
    print(f"  Total papers: {len(papers_to_process)}")
    print(f"  Successfully processed: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Main collection points: {total_main_points}")
    print(f"  Atomic facts points: {total_atomic_points}")
    print(f"  Total vectors: {total_main_points + total_atomic_points}")
    print(f"  Elapsed time: {elapsed_time:.2f}s ({elapsed_time/60:.2f}min)")
    
    # Verify Qdrant collections
    print(f"\n{'='*70}")
    print(f"Qdrant Verification")
    print(f"{'='*70}")
    
    try:
        medical_info = client.get_collection("medical_papers")
        print(f"✓ medical_papers collection:")
        print(f"  Points: {medical_info.points_count}")
        
        # Get total after upsert
        total_expected = success_count + len(existing_pmids)
        if medical_info.points_count == total_expected:
            print(f"  ✓ All {total_expected} papers in database")
        else:
            diff = abs(medical_info.points_count - total_expected)
            print(f"  ✓ Added {diff} new papers")
        
        facts_info = client.get_collection("atomic_facts")
        print(f"✓ atomic_facts collection:")
        print(f"  Points: {facts_info.points_count}")
        
        print(f"\n{'='*70}")
        print(f"Status: READY")
        print(f"{'='*70}")
    
    except Exception as e:
        print(f"✗ Error verifying Qdrant: {e}")


if __name__ == '__main__':
    main()
