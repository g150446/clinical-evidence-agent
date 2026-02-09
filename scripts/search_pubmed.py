#!/usr/bin/env python3
"""
PubMed検索スクリプト
肥満治療関連の論文を検索してPMIDリストを取得
"""

import requests
import json
import time
from xml.etree import ElementTree as ET
from pathlib import Path

# PubMed E-utilities APIエンドポイント
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# 検索クエリ定義
SEARCH_QUERIES = {
    "pharmacologic": {
        "query": '(obesity[MeSH Terms]) AND (drug therapy[MeSH Terms]) AND ("2020/01/01"[Date - Publication] : "3000"[Date - Publication]) AND (Randomized Controlled Trial[Publication Type] OR Meta-Analysis[Publication Type])',
        "target_count": 100
    },
    "surgical": {
        "query": '(obesity[MeSH Terms]) AND (bariatric surgery[MeSH Terms]) AND ("2020/01/01"[Date - Publication] : "3000"[Date - Publication]) AND (Randomized Controlled Trial[Publication Type] OR Meta-Analysis[Publication Type])',
        "target_count": 100
    },
    "lifestyle": {
        "query": '(obesity[MeSH Terms]) AND (diet therapy[MeSH Terms] OR exercise therapy[MeSH Terms] OR lifestyle[MeSH Terms]) AND ("2020/01/01"[Date - Publication] : "3000"[Date - Publication]) AND (Randomized Controlled Trial[Publication Type] OR Meta-Analysis[Publication Type])',
        "target_count": 100
    }
}


def search_pubmed(query, retmax=100):
    """
    PubMedで検索を実行し、PMIDリストを取得
    """
    params = {
        'db': 'pubmed',
        'term': query,
        'retmax': retmax,
        'retmode': 'xml',
        'sort': 'relevance'
    }
    
    try:
        response = requests.get(ESEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        
        # XMLをパース
        root = ET.fromstring(response.content)
        
        # PMIDを抽出
        pmids = []
        for id_elem in root.findall('.//IdList/Id'):
            pmids.append(id_elem.text)
        
        # 検索結果数を取得
        count_elem = root.find('.//Count')
        total_count = int(count_elem.text) if count_elem is not None else 0
        
        return {
            'pmids': pmids,
            'total_count': total_count,
            'retrieved_count': len(pmids)
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching PubMed: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None


def fetch_paper_details(pmids):
    """
    PMIDリストから論文の詳細情報を取得
    """
    if not pmids:
        return []
    
    params = {
        'db': 'pubmed',
        'id': ','.join(pmids),
        'retmode': 'xml'
    }
    
    try:
        response = requests.get(EFETCH_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching paper details: {e}")
        return None


def main():
    """
    メイン処理：3つの領域で検索を実行
    """
    results = {}
    
    print("=" * 60)
    print("PubMed 肥満治療論文検索")
    print("=" * 60)
    
    for domain, config in SEARCH_QUERIES.items():
        print(f"\n検索中: {domain}")
        print(f"クエリ: {config['query'][:80]}...")
        
        result = search_pubmed(config['query'], config['target_count'])
        
        if result:
            print(f"  検索結果: {result['total_count']}件")
            print(f"  取得件数: {result['retrieved_count']}件")
            
            results[domain] = {
                'pmids': result['pmids'],
                'total_count': result['total_count'],
                'query': config['query']
            }
            
            # レート制限対策
            time.sleep(0.5)
        else:
            print(f"  エラー: 検索に失敗しました")
            results[domain] = None
    
    # 結果を保存
    output_file = Path('data/obesity/search_results.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"検索結果を保存しました: {output_file}")
    print(f"{'=' * 60}")
    
    # サマリーを表示
    total_pmids = sum(len(r['pmids']) for r in results.values() if r)
    print(f"\n合計取得論文数: {total_pmids}件")
    for domain, result in results.items():
        if result:
            print(f"  - {domain}: {len(result['pmids'])}件")


if __name__ == '__main__':
    main()
