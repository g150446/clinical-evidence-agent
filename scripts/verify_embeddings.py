#!/usr/bin/env python3
"""
Embedding Verification Script
Quick health check for the Qdrant embedding database
"""

from qdrant_client import QdrantClient
from pathlib import Path


def verify_embeddings():
    """Verify embeddings in Qdrant collections"""

    print("\n" + "="*70)
    print("Embedding Database Verification")
    print("="*70 + "\n")

    # Initialize client
    try:
        client = QdrantClient(path="./qdrant_medical_db")
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        return False

    # Check medical_papers collection
    print("Medical Papers Collection:")
    print("-" * 70)

    try:
        papers_result = client.scroll(
            collection_name="medical_papers",
            limit=10000,
            with_payload=True,
            with_vectors=True
        )
        papers = papers_result[0]

        print(f"  Total points: {len(papers)}")

        # Check unique PMIDs
        pmids = set()
        for point in papers:
            pmid = point.payload.get('paper_id', '')
            if pmid:
                pmids.add(pmid)

        print(f"  Unique PMIDs: {len(pmids)}")

        if len(papers) != len(pmids):
            print(f"  ⚠️  Warning: {len(papers) - len(pmids)} duplicate points")

        # Check sample paper for named vectors
        if papers:
            sample = papers[0]
            vectors = sample.vector
            expected_vectors = ['sapbert_pico', 'e5_pico', 'e5_questions_en', 'e5_questions_ja']

            print(f"\n  Sample paper: {sample.payload.get('paper_id', 'unknown')}")
            print(f"  Named vectors: {list(vectors.keys())}")

            all_vectors_present = True
            for vec_name in expected_vectors:
                if vec_name in vectors:
                    dim = len(vectors[vec_name])
                    expected_dim = 768 if 'sapbert' in vec_name else 1024
                    status = "✓" if dim == expected_dim else "✗"
                    print(f"    {status} {vec_name}: {dim} dimensions")
                    if dim != expected_dim:
                        all_vectors_present = False
                else:
                    print(f"    ✗ {vec_name}: MISSING")
                    all_vectors_present = False

            if not all_vectors_present:
                print("  ⚠️  Warning: Some vectors missing or wrong dimensions")

    except Exception as e:
        print(f"  ❌ Error querying medical_papers: {e}")
        return False

    # Check atomic_facts collection
    print("\n" + "-" * 70)
    print("Atomic Facts Collection:")
    print("-" * 70)

    try:
        facts_result = client.scroll(
            collection_name="atomic_facts",
            limit=10000,
            with_payload=True,
            with_vectors=True
        )
        facts = facts_result[0]

        print(f"  Total points: {len(facts)}")

        if len(pmids) > 0:
            avg_facts = len(facts) / len(pmids)
            print(f"  Average per paper: {avg_facts:.1f}")

        # Check sample atomic fact
        if facts:
            sample_fact = facts[0]
            fact_vec = sample_fact.vector

            print(f"\n  Sample atomic fact:")
            print(f"  Paper ID: {sample_fact.payload.get('paper_id', 'unknown')}")
            print(f"  Fact text: {sample_fact.payload.get('fact_text', '')[:80]}...")
            print(f"  Named vectors: {list(fact_vec.keys())}")

            if 'sapbert_fact' in fact_vec:
                dim = len(fact_vec['sapbert_fact'])
                status = "✓" if dim == 768 else "✗"
                print(f"    {status} sapbert_fact: {dim} dimensions")
            else:
                print(f"    ✗ sapbert_fact: MISSING")

    except Exception as e:
        print(f"  ❌ Error querying atomic_facts: {e}")
        return False

    # Compare with file system
    print("\n" + "-" * 70)
    print("File System Comparison:")
    print("-" * 70)
    
    SUBSECTIONS = {
        'pharmacologic': ['glp1_receptor_agonists', 'guidelines_and_reviews', 'novel_agents'],
        'surgical': ['procedures_and_outcomes', 'metabolic_effects', 'complications_safety'],
        'lifestyle': ['dietary_interventions', 'physical_activity', 'behavioral_therapy']
    }
    
    domains = ['pharmacologic', 'surgical', 'lifestyle']
    total_files = 0
    
    for domain in domains:
        domain_files = 0
        
        for subsection in SUBSECTIONS[domain]:
            papers_dir = Path(f'data/obesity/{domain}/{subsection}/papers')
            if papers_dir.exists():
                count = len(list(papers_dir.glob('PMID_*.json')))
                print(f"  {domain}/{subsection}: {count} structured papers")
                domain_files += count
            else:
                print(f"  {domain}/{subsection}: directory not found")
        
        print(f"  {domain}: {domain_files} total structured papers")
        total_files += domain_files
    
    print(f"\n  Total structured papers: {total_files}")
    print(f"  Total in Qdrant: {len(pmids)}")

    if total_files == len(pmids):
        print(f"  ✓ Match: All papers embedded")
    else:
        print(f"  ⚠️  Mismatch: {total_files - len(pmids)} papers not embedded")

    # Final status
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    status = "✓ HEALTHY" if (
        len(papers) == total_files and
        len(papers) == len(pmids) and
        len(facts) > 0
    ) else "⚠️  NEEDS ATTENTION"

    print(f"  Database status: {status}")
    print(f"  Papers: {len(pmids)}/{total_files}")
    print(f"  Atomic facts: {len(facts)}")
    print("="*70 + "\n")

    return status == "✓ HEALTHY"


if __name__ == '__main__':
    verify_embeddings()
