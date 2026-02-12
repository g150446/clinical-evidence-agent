#!/usr/bin/env python3
"""
Qdrantデータ移行スクリプト

sourceバックエンドからdestinationバックエンドへコレクションをコピー
"""

import argparse
import os
import sys
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


def migrate_collection(source_url, dest_url, collection_name):
    """コレクションをsourceからdestへコピー"""
    print(f"Copying collection: {collection_name}")

    source_client = QdrantClient(url=source_url)
    dest_client = QdrantClient(url=dest_url)

    # Sourceからすべてのポイントを取得
    scroll_result = source_client.scroll(
        collection_name=collection_name,
        limit=10000,
        with_payload=True,
        with_vectors=True
    )

    points = scroll_result[0]
    print(f"Found {len(points)} points to migrate")

    if len(points) == 0:
        print("No points to migrate")
        return

    # Destinationにコレクションを作成（既存の場合は削除して再作成）
    try:
        dest_client.delete_collection(collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except Exception as e:
        if "not found" not in str(e).lower():
            print(f"Warning deleting collection: {e}")

    # Sourceのコレクション情報を取得
    collection_info = source_client.get_collection(collection_name)

    # Destinationにコレクションを作成
    dest_client.create_collection(
        collection_name=collection_name,
        vectors_config=collection_info.config.params.vectors
    )
    print(f"Created collection: {collection_name}")

    # ポイントをアップロード
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]

        # ポイントをPointStructに変換
        point_structs = []
        for point in batch:
            if isinstance(point, PointStruct):
                point_structs.append(point)
            else:
                # 既存のポイント形式を変換
                point_structs.append(PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=point.payload
                ))

        dest_client.upsert(
            collection_name=collection_name,
            points=point_structs
        )
        print(f"Uploaded {min(i+batch_size, len(points))}/{len(points)} points")

    print(f"Migration complete: {collection_name}")


def main():
    parser = argparse.ArgumentParser(description='Migrate Qdrant collections between backends')
    parser.add_argument('--source', required=True, help='Source Qdrant URL (e.g., http://macbook-m1.tailnet-name.ts.net:6333)')
    parser.add_argument('--dest', required=True, help='Destination Qdrant URL (e.g., http://mac-dev1.tailnet-name.ts.net:6333)')
    parser.add_argument('--collections', nargs='+', default=['medical_papers', 'atomic_facts'], help='Collections to migrate (default: medical_papers atomic_facts)')
    args = parser.parse_args()

    print(f"Source: {args.source}")
    print(f"Destination: {args.dest}")
    print(f"Collections: {', '.join(args.collections)}")
    print()

    for collection in args.collections:
        try:
            migrate_collection(args.source, args.dest, collection)
        except Exception as e:
            print(f"Error migrating {collection}: {e}")
            sys.exit(1)

    print("\nAll migrations completed successfully!")


if __name__ == '__main__':
    main()
