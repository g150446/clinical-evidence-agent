#!/usr/bin/env python3
"""
Qdrant Cloud 初期化スクリプト
Qdrant Cloudのコレクションを削除し、再作成する
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os
import sys
from dotenv import load_dotenv


def load_env():
    """Load environment variables from .env file"""
    load_dotenv()
    
    cloud_url = os.getenv('QDRANT_CLOUD_ENDPOINT')
    cloud_api_key = os.getenv('QDRANT_CLOUD_API_KEY')
    
    if not cloud_url or not cloud_api_key:
        print("✗ Error: QDRANT_CLOUD_ENDPOINT or QDRANT_CLOUD_API_KEY not found in .env")
        print("Please ensure these variables are set in your .env file:")
        print("  QDRANT_CLOUD_ENDPOINT=https://your-cluster.cloud.qdrant.io")
        print("  QDRANT_CLOUD_API_KEY=your-api-key")
        sys.exit(1)
    
    return cloud_url, cloud_api_key


def connect_to_cloud(cloud_url, cloud_api_key):
    """Connect to Qdrant Cloud"""
    print("Connecting to Qdrant Cloud...")
    print(f"  Endpoint: {cloud_url}")
    
    try:
        client = QdrantClient(url=cloud_url, api_key=cloud_api_key)
        # Test connection
        collections = client.get_collections()
        print(f"✓ Connected to Qdrant Cloud")
        print(f"  Existing collections: {[c.name for c in collections.collections]}")
        return client
    except Exception as e:
        print(f"✗ Error connecting to Qdrant Cloud: {e}")
        sys.exit(1)


def delete_collections(client):
    """Delete existing collections"""
    print("\n" + "="*70)
    print("Deleting existing collections...")
    print("="*70)
    
    collections_to_delete = ["medical_papers", "atomic_facts"]
    
    for collection_name in collections_to_delete:
        try:
            client.delete_collection(collection_name)
            print(f"✓ Deleted collection: {collection_name}")
        except Exception as e:
            if "doesn't exist" in str(e).lower() or "not found" in str(e).lower():
                print(f"  Collection {collection_name} does not exist (skipped)")
            else:
                print(f"  Error deleting {collection_name}: {e}")


def create_collections(client):
    """Create new collections with proper vector configurations"""
    print("\n" + "="*70)
    print("Creating collections...")
    print("="*70)
    
    # medical_papers collection
    print("\nCreating medical_papers collection...")
    client.create_collection(
        collection_name="medical_papers",
        vectors_config={
            # SapBERT: Medical concept understanding (English PICO)
            "sapbert_pico": VectorParams(size=768, distance=Distance.COSINE),
            
            # multilingual-e5: PICO (language-agnostic)
            "e5_pico": VectorParams(size=1024, distance=Distance.COSINE),
            
            # multilingual-e5: English question matching (average)
            "e5_questions_en": VectorParams(size=1024, distance=Distance.COSINE)
        }
    )
    print("✓ Created collection: medical_papers")
    print("  Vectors:")
    print("    - sapbert_pico: 768-dim (COSINE)")
    print("    - e5_pico: 1024-dim (COSINE)")
    print("    - e5_questions_en: 1024-dim (COSINE)")
    
    # atomic_facts collection
    print("\nCreating atomic_facts collection...")
    client.create_collection(
        collection_name="atomic_facts",
        vectors_config={
            # SapBERT: Medical concept understanding (atomic facts)
            "sapbert_fact": VectorParams(size=768, distance=Distance.COSINE)
        }
    )
    print("✓ Created collection: atomic_facts")
    print("  Vectors:")
    print("    - sapbert_fact: 768-dim (COSINE)")


def verify_collections(client):
    """Verify created collections"""
    print("\n" + "="*70)
    print("Verification")
    print("="*70)
    
    try:
        # Verify medical_papers
        medical_info = client.get_collection("medical_papers")
        print(f"\n✓ medical_papers collection:")
        print(f"  Points: {medical_info.points_count}")
        print(f"  Vector configs: {len(medical_info.config.params.vectors)} vectors")
        
        # Verify atomic_facts
        facts_info = client.get_collection("atomic_facts")
        print(f"\n✓ atomic_facts collection:")
        print(f"  Points: {facts_info.points_count}")
        print(f"  Vector configs: {len(facts_info.config.params.vectors)} vectors")
        
        print(f"\n{'='*70}")
        print("Qdrant Cloud Initialization Complete")
        print(f"{'='*70}")
        print("\nCollections are ready for embedding generation.")
        print("Run: python3 scripts/generate_embeddings.py --cloud")
        
    except Exception as e:
        print(f"\n✗ Error verifying collections: {e}")
        sys.exit(1)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Initialize Qdrant Cloud collections (delete and recreate)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize with confirmation prompt
  python3 scripts/setup_qdrant_cloud.py
  
  # Initialize without confirmation (force)
  python3 scripts/setup_qdrant_cloud.py --force
        """
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompt and proceed with initialization'
    )
    args = parser.parse_args()
    
    print("="*70)
    print("Qdrant Cloud Initialization")
    print("="*70)
    print("\nThis script will:")
    print("  1. Delete existing 'medical_papers' collection")
    print("  2. Delete existing 'atomic_facts' collection")
    print("  3. Create new collections with proper vector configurations")
    print("\n⚠️  WARNING: All existing data in Qdrant Cloud will be lost!")
    
    # Confirmation prompt (unless --force is used)
    if not args.force:
        print("\n" + "="*70)
        response = input("Do you want to proceed? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("\nInitialization cancelled.")
            sys.exit(0)
    
    # Load environment variables
    cloud_url, cloud_api_key = load_env()
    
    # Connect to Qdrant Cloud
    client = connect_to_cloud(cloud_url, cloud_api_key)
    
    # Delete existing collections
    delete_collections(client)
    
    # Create new collections
    create_collections(client)
    
    # Verify collections
    verify_collections(client)


if __name__ == '__main__':
    main()
