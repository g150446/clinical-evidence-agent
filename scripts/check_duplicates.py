#!/usr/bin/env python3
"""
重複チェックスクリプト
3領域間の重複PMIDを検出して除外
"""

import json
from pathlib import Path
from collections import defaultdict

def check_duplicates():
    # 検索結果を読み込み
    with open('data/obesity/search_results.json', 'r') as f:
        results = json.load(f)
    
    # 全PMIDを収集
    all_pmids = defaultdict(list)
    for domain, data in results.items():
        if data and 'pmids' in data:
            for pmid in data['pmids']:
                all_pmids[pmid].append(domain)
    
    # 重複を検出
    duplicates = {pmid: domains for pmid, domains in all_pmids.items() if len(domains) > 1}
    
    print("=" * 60)
    print("重複チェック結果")
    print("=" * 60)
    
    if duplicates:
        print(f"\n重複検出: {len(duplicates)}件のPMIDが複数領域に存在")
        for pmid, domains in sorted(duplicates.items()):
            print(f"  PMID {pmid}: {', '.join(domains)}")
    else:
        print("\n重複なし: 各PMIDは一意に1つの領域に属しています")
    
    # 重複を除外した統計
    print(f"\n{'=' * 60}")
    print("重複除外後の統計")
    print("=" * 60)
    
    unique_pmids = {}
    for domain, data in results.items():
        if data and 'pmids' in data:
            # 重複PMIDを除外（最初の領域に残す）
            unique = [pmid for pmid in data['pmids'] if all_pmids[pmid] == [domain] or all_pmids[pmid][0] == domain]
            unique_pmids[domain] = unique
            print(f"{domain}: {len(data['pmids'])}件 → {len(unique)}件（重複除外）")
    
    total_unique = sum(len(pmids) for pmids in unique_pmids.values())
    print(f"\n合計: {total_unique}件（重複除外後）")
    
    # 重複除外後の結果を保存
    cleaned_results = {}
    for domain, data in results.items():
        if data:
            cleaned_results[domain] = {
                'pmids': unique_pmids[domain],
                'total_count': data['total_count'],
                'query': data['query'],
                'excluded_duplicates': len(data['pmids']) - len(unique_pmids[domain])
            }
    
    # 重複情報も保存
    output = {
        'domains': cleaned_results,
        'duplicates': duplicates,
        'summary': {
            'total_before': sum(len(data['pmids']) for data in results.values() if data),
            'total_after': total_unique,
            'duplicates_removed': len(duplicates)
        }
    }
    
    output_file = Path('data/obesity/search_results_cleaned.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"重複除外後の結果を保存しました: {output_file}")
    print("=" * 60)

if __name__ == '__main__':
    check_duplicates()
