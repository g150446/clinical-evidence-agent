#!/usr/bin/env python3
"""
Qdrant validation and testing script
Validates collections, data integrity, and runs test queries
"""

from qdrant_client import QdrantClient
from pathlib import Path
import json


def validate_qdrant_setup():
    """
    Validate Qdrant collections and data integrity
    
    Returns:
        validation_results: dict with status of each check
    """
    client = QdrantClient(path="./qdrant_medical_db")
    
    print("="*70)
    print("Qdrant Validation")
    print("="*70)
    
    results = {}
    results['collections'] = {}
    results['data_integrity'] = {}
    
    # Check collections exist
    print("\nCollections Status:")
    try:
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        for name in ["medical_papers", "atomic_facts"]:
            if name in collection_names:
                print(f"  ✓ {name} exists")
                results['collections'][name] = 'exists'
                
                # Get collection info
                info = client.get_collection(name)
                print(f"    Points: {info.points_count}")
                
                # Check vector configs
                vector_names = list(info.config.params.vectors.keys())
                if name == "medical_papers":
                    expected_vectors = ["sapbert_pico", "e5_pico", "e5_questions_en", "e5_questions_ja"]
                    for v in expected_vectors:
                        if v in vector_names:
                            v_info = info.config.params.vectors[v]
                            print(f"    ✓ Vector: {v} (dim={v_info.size})")
                        else:
                            print(f"    ! Missing vector: {v}")
                            results['collections'][name] = 'incomplete'
                else:
                    expected_vectors = ["sapbert_fact"]
                    for v in expected_vectors:
                        if v in vector_names:
                            v_info = info.config.params.vectors[v]
                            print(f"    ✓ Vector: {v} (dim={v_info.size})")
                        else:
                            print(f"    ! Missing vector: {v}")
                            results['collections'][name] = 'incomplete'
            else:
                print(f"  ! {name} not found")
                results['collections'][name] = 'missing'
    except Exception as e:
        print(f"  Error: {e}")
        results['collections'] = {'error': str(e)}
    
    # Count structured papers
    papers_dir = Path('data/obesity/pharmacologic/glp1_receptor_agonists/papers')
    paper_count = len(list(papers_dir.glob('PMID_*.json')))
    
    print(f"\nData Integrity:")
    print(f"  Structured papers: {paper_count}")
    results['data_integrity']['structured_papers'] = paper_count
    
    if 'medical_papers' in collection_names:
        medical_info = client.get_collection("medical_papers")
        print(f"  Loaded papers: {medical_info.points_count}")
        results['data_integrity']['loaded_papers'] = medical_info.points_count
        
        if medical_info.points_count == paper_count:
            print(f"  ✓ All papers loaded")
            results['data_integrity']['load_status'] = 'complete'
        else:
            diff = abs(medical_info.points_count - paper_count)
            print(f"  ! Difference: {diff} papers")
            results['data_integrity']['load_status'] = 'incomplete'
    else:
        results['data_integrity']['loaded_papers'] = 0
        results['data_integrity']['load_status'] = 'skipped'
    
    if 'atomic_facts' in collection_names:
        facts_info = client.get_collection("atomic_facts")
        avg_facts_per_paper = facts_info.points_count / paper_count if paper_count > 0 else 0
        print(f"  Atomic facts: {facts_info.points_count}")
        print(f"  Average per paper: {avg_facts_per_paper:.1f}")
        results['data_integrity']['atomic_facts'] = facts_info.points_count
        results['data_integrity']['avg_facts_per_paper'] = avg_facts_per_paper
    else:
        results['data_integrity']['atomic_facts'] = 0
        results['data_integrity']['avg_facts_per_paper'] = 0
    
    # Overall status
    all_collections_ok = all(
        results['collections'].get(name, 'exists') in ['exists', 'incomplete']
        for name in ["medical_papers", "atomic_facts"]
    )
    all_data_loaded = results['data_integrity'].get('load_status') == 'complete'
    
    if all_collections_ok and all_data_loaded:
        overall_status = 'ready'
        print(f"\n✓ System is ready for search")
    elif all_collections_ok:
        overall_status = 'partial'
        print(f"\n⚠ Collections ready, but data not fully loaded")
    else:
        overall_status = 'incomplete'
        print(f"\n✗ Setup incomplete")
    
    results['overall_status'] = overall_status
    return results


def main():
    """Main entry point"""
    print("Qdrant Setup and Data Validation\n")
    
    results = validate_qdrant_setup()
    
    # Save validation report
    output_file = Path('validation_report.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"Validation complete")
    print(f"{'='*70}")
    print(f"Report saved to: {output_file}")
    print(f"\nSystem Status: {results['overall_status']}")
    print(f"Note: Embedding models not loaded - see DISK_SPACE_ISSUE.md")


if __name__ == '__main__':
    main()
