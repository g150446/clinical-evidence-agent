#!/usr/bin/env python3
"""
Generate embeddings for all obesity treatment papers
Processes pharmacologic, surgical, and lifestyle domains sequentially
"""

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json
import numpy as np
import time
import uuid
from openai import OpenAI

# Initialize Qdrant client (use local database)
# Note: Initialize client without path to ensure clean state
client = QdrantClient()

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


def process_paper(paper_path, paper_id, processed_pmids):
    """Process single paper and generate embeddings
    
    Returns:
        success: bool
        paper_id: str
        points_count: int (main collection + atomic facts)
    """
    
    try:
        # Load structured data
        with open(paper_path, 'r', encoding='utf-8') as f:
            paper = json.load(f)
        
        # Extract data
        paper_id_orig = paper.get('paper_id', '')
        pico = paper['language_independent_core'].get('pico_en', {})
        atomic_facts = paper['language_independent_core'].get('atomic_facts_en', [])
        metadata = paper.get('metadata', {})
        
        # Check for generated questions
        if 'multilingual_interface' not in paper:
            print(f"  ! Missing multilingual_interface in {paper_id}")
            return False, paper_path.stem, 0
        
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
                        "paper_id": paper_id_orig,
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
                        "paper_id": paper_id_orig,
                        "fact_text": fact,
                        "fact_index": idx
                    }
                )
            )
        
        client.upsert(
            collection_name="atomic_facts",
            points=atomic_points
        )
        
        return True, paper_id, 1 + len(atomic_points)
        
    except Exception as e:
        print(f"  ✗ Error processing {paper_path.name}: {e}")
        return False, paper_path.stem, 0


def main():
    """Process all structured papers"""
    
    print("="*70)
    print("Qdrant Embedding Generation")
    print("="*70)
    
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
        
        success, paper_id, points = process_paper(paper_file, paper_id, existing_pmids)
        
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
            
            # Stop on error (Option B)
            print(f"\n✗ Error detected. Stopping processing as per Option B.")
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
