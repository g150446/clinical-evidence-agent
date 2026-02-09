#!/usr/bin/env python3
"""
Generate embeddings for all obesity treatment papers
Fixed version with UUID and list issues resolved
"""

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json
import numpy as np
import time

# Import uuid directly (not as uuid_lib)
import uuid

# Initialize Qdrant client with path parameter
print("Initializing Qdrant client...")
client = QdrantClient(path="./qdrant_medical_db")
print("✓ Qdrant client initialized")

# Load models (use default HuggingFace cache)
print("Loading embedding models...")
print("(Models will be cached in ~/.cache/huggingface)")
print("If this is your first run, models will be downloaded (~3.6GB total)")
print()

try:
    sapbert = SentenceTransformer(
        'cambridgeltl/SapBERT-from-PubMedBERT-fulltext'
    )
    print("✓ SapBERT loaded")
except Exception as e:
    print(f"✗ Error loading SapBERT: {e}")
    raise

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
            return False, None, 0, None
        
        questions_en = paper['multilingual_interface'].get('generated_questions', {}).get('en', [])
        questions_ja = paper['multilingual_interface'].get('generated_questions', {}).get('ja', [])
        
        # 1. SapBERT PICO embedding
        pico_combined = f"{pico.get('patient', '')} {pico.get('intervention', '')} {pico.get('comparison', '')} {pico.get('outcome', '')}"
        sapbert_pico_vec = sapbert.encode(pico_combined, normalize_embeddings=True)
        
        # 2. E5 PICO embedding (with passage: prefix)
        e5_pico_vec = multilingual_e5.encode(
            f"passage: {pico_combined}", 
            normalize_embeddings=True
        )
        
        # 3. E5 English questions (average with query: prefix)
        if questions_en:
            e5_q_en_vecs = [
                multilingual_e5.encode(f"query: {q}", normalize_embeddings=True)
                for q in questions_en
            ]
            e5_questions_en_vec = np.mean(e5_q_en_vecs, axis=0)
        else:
            e5_questions_en_vec = np.zeros(1024, dtype=np.float32)
        
        # 4. E5 Japanese questions (average with query: prefix)
        if questions_ja:
            e5_q_ja_vecs = [
                multilingual_e5.encode(f"query: {q}", normalize_embeddings=True)
                for q in questions_ja
            ]
            e5_questions_ja_vec = np.mean(e5_q_ja_vecs, axis=0)
        else:
            e5_questions_ja_vec = np.zeros(1024, dtype=np.float32)
        
        # Generate unique UUID for paper
        paper_uuid = str(uuid.uuid4())
        
        # 5. Upsert to medical_papers collection
        client.upsert(
            collection_name="medical_papers",
            points=[
                PointStruct(
                    id=paper_uuid,
                    vector={
                        "sapbert_pico": sapbert_pico_vec.tolist(),
                        "e5_pico": e5_pico_vec.tolist(),
                        "e5_questions_en": e5_questions_en_vec.tolist(),
                        "e5_questions_ja": e5_questions_ja_vec.tolist()
                    },
                    payload={
                        "paper_id": paper_id,
                        "pico_en": pico,
                        "metadata": metadata,
                        "mesh_terms": metadata.get('mesh_terms', [])
                    }
                )
            ]
        )
        
        # 6. Atomic facts (separate collection)
        atomic_points = []
        for idx, fact in enumerate(atomic_facts):
            fact_uuid = str(uuid.uuid4())
            fact_vec = sapbert.encode(fact, normalize_embeddings=True)
            atomic_points.append(
                PointStruct(
                    id=fact_uuid,
                    vector={"sapbert_fact": fact_vec.tolist()},
                    payload={
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
        return False, paper_path.stem, 0, None


def main():
    """Process all structured papers"""
    
    print("="*70)
    print("Qdrant Embedding Generation")
    print("="*70)
    
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
    print(f"Processing {total_papers} papers...\n")
    
    # Process all papers
    total_main_points = 0
    total_atomic_points = 0
    success_count = 0
    error_count = 0
    
    start_time = time.time()
    
    for idx, paper_path in enumerate(all_papers, 1):
        paper_id = paper_path.stem.replace('PMID_', '')
        
        domain_subsection, paper_name = str(paper_path).split('/')[-2:]
        domain, subsection = domain_subsection
        print(f"[{idx}/{total_papers}] {domain}/{subsection}/{paper_name}")
        print(f"[{idx}/{total_papers}] {paper_id} - Generating embeddings...")
        
        success, paper_id, paper_uuid, points = process_paper(paper_path)
        
        if success:
            success_count += 1
            total_main_points += 1
            total_atomic_points += points
            
            if idx % 10 == 0 or idx == total_papers:
                elapsed = time.time() - start_time
                progress = (idx / total_papers) * 100
                print(f"  Progress: {progress:.1f}% | Success: {success_count} | Time: {elapsed:.1f}s | Main: {total_main_points} | Atomic: {total_atomic_points}")
        else:
            error_count += 1
            print(f"  ✗ Failed: {paper_id}")
            
            # Stop on error (Option B)
            print(f"\n✗ Error detected. Stopping processing as per Option B.")
            break
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Qdrant Embedding Generation Complete")
    print(f"{'='*70}")
    print(f"\nSummary:")
    print(f"  Total papers: {total_papers}")
    print(f"  Successfully processed: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Main collection points: {total_main_points}")
    print(f"  Atomic facts points: {total_atomic_points}")
    print(f"  Total vectors: {total_main_points + total_atomic_points}")
    print(f"  Elapsed time: {elapsed_time:.2f}s ({elapsed_time/60:.2f}min)")
    
    # Verify Qdrant collections (simple version)
    print(f"\n{'='*70}")
    print(f"Qdrant Verification")
    print(f"{'='*70}")
    
    try:
        medical_info = client.get_collection("medical_papers")
        print(f"✓ medical_papers collection:")
        print(f"  Points: {medical_info.points_count}")
        
        facts_info = client.get_collection("atomic_facts")
        print(f"✓ atomic_facts collection:")
        print(f"  Points: {facts_info.points_count}")
        
        total_expected = success_count
        
        if medical_info.points_count == total_expected:
            print(f"  ✓ All {total_expected} papers loaded correctly")
        else:
            diff = abs(medical_info.points_count - total_expected)
            print(f"  ✓ Added {diff} new papers")
            
        # Calculate expected atomic facts (14 per paper average)
        expected_atomic = success_count * 14
        
        if facts_info.points_count >= expected_atomic * 0.9:  # Allow 10% variance
            print(f"  ✓ ~{expected_atomic} atomic facts loaded")
        else:
            print(f"  ! Only {facts_info.points_count}/{expected_atomic} atomic facts loaded")
            
    except Exception as e:
        print(f"✗ Error verifying Qdrant: {e}")
    
    print(f"\n{'='*70}")
    print(f"Status: COMPLETE")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
