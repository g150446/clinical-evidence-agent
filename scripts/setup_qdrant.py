#!/usr/bin/env python3
"""
Qdrant collections setup with Named Vectors
Creates medical_papers and atomic_facts collections
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from pathlib import Path


def setup_qdrant(db_path="./qdrant_medical_db"):
    """
    Create Qdrant collections with Named Vectors
    
    Collection: medical_papers (4 named vectors)
      - sapbert_pico: 768-dim (SapBERT embedding of PICO)
      - e5_pico: 1024-dim (multilingual-e5 embedding of PICO)
      - e5_questions_en: 1024-dim (avg of English questions)
      - e5_questions_ja: 1024-dim (avg of Japanese questions)
    
    Collection: atomic_facts (1 named vector)
      - sapbert_fact: 768-dim (SapBERT embedding of each atomic fact)
    """
    client = QdrantClient(path=db_path)
    
    print("="*70)
    print("Qdrant Collections Setup")
    print("="*70)
    
    # Recreate collections (delete if exists)
    try:
        client.delete_collection("medical_papers")
        print("✓ Deleted existing collection: medical_papers")
    except Exception:
        pass
    
    try:
        client.delete_collection("atomic_facts")
        print("✓ Deleted existing collection: atomic_facts")
    except Exception:
        pass
    
    # Main collection: medical_papers with 4 named vectors
    client.create_collection(
        collection_name="medical_papers",
        vectors_config={
            # SapBERT: Medical concept understanding (English PICO)
            "sapbert_pico": VectorParams(size=768, distance=Distance.COSINE),
            
            # multilingual-e5: PICO (language-agnostic)
            "e5_pico": VectorParams(size=1024, distance=Distance.COSINE),
            
            # multilingual-e5: English question matching (average)
            "e5_questions_en": VectorParams(size=1024, distance=Distance.COSINE),
            
            # multilingual-e5: Japanese question matching (average)
            "e5_questions_ja": VectorParams(size=1024, distance=Distance.COSINE)
        }
    )
    print("✓ Created collection: medical_papers (4 named vectors)")
    
    # Sub collection: atomic_facts
    client.create_collection(
        collection_name="atomic_facts",
        vectors_config={
            "sapbert_fact": VectorParams(size=768, distance=Distance.COSINE)
        }
    )
    print("✓ Created collection: atomic_facts")
    
    # Display collection info
    medical_info = client.get_collection("medical_papers")
    facts_info = client.get_collection("atomic_facts")
    
    print(f"\nmedical_papers config:")
    print(f"  Points: {medical_info.points_count}")
    print(f"  Vector configs: {len(medical_info.config.params.vectors)} vectors")
    
    print(f"\natomic_facts config:")
    print(f"  Points: {facts_info.points_count}")
    print(f"  Vector configs: {len(facts_info.config.params.vectors)} vectors")
    
    print(f"\n{'='*70}")
    print("Qdrant Setup Complete")
    print(f"{'='*70}\n")
    
    return client


if __name__ == '__main__':
    setup_qdrant()
