#!/usr/bin/env python3
"""
クエリ変換のテストスクリプト
改善されたPubMed検索クエリ変換をテストする
"""

import os
import sys
from evidence_service import EvidenceService
from pubmed_client import PubMedClient

def test_query_reformulation():
    """クエリ変換のテスト"""

    # PubMedクライアントとEvidenceServiceを初期化
    client = PubMedClient()
    service = EvidenceService(client, max_papers=10)

    # テストケース
    test_cases = [
        {
            'question': '経口のセマグルチドと注射のセマグルチドでは体重減少効果に違いはありますか',
            'expected_pmid': '37385278',  # OASIS-1試験
            'description': 'ユーザーの実際の質問（最重要テスト）'
        },
        {
            'question': 'メトホルミンの副作用は何ですか',
            'expected_pmid': None,
            'description': '日本語質問（副作用検索）'
        },
        {
            'question': '2型糖尿病の治療法は',
            'expected_pmid': None,
            'description': '日本語質問（治療法検索）'
        },
        {
            'question': 'What is metformin used for?',
            'expected_pmid': None,
            'description': '英語質問（既存機能の確認）'
        }
    ]

    print("=" * 80)
    print("クエリ変換テスト")
    print("=" * 80)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n【テスト{i}】 {test_case['description']}")
        print(f"質問: {test_case['question']}")
        print("-" * 80)

        # エビデンス検索を実行
        evidence = service.retrieve_evidence(test_case['question'], max_papers=10)

        print(f"✓ 検索クエリ: {evidence['search_query']}")
        print(f"✓ 検索結果: {evidence['total_found']}件該当")
        print(f"✓ 取得論文数: {len(evidence['papers'])}件")

        if evidence['status'] == 'success' and evidence['papers']:
            print(f"\n論文リスト:")
            for j, paper in enumerate(evidence['papers'], 1):
                print(f"  [{j}] PMID: {paper['pmid']}")
                print(f"      Title: {paper['title'][:80]}...")
                print(f"      Journal: {paper['journal']} ({paper['pubdate']})")

                # 期待されるPMIDが含まれているか確認
                if test_case['expected_pmid'] and paper['pmid'] == test_case['expected_pmid']:
                    print(f"      ✅ 期待されたPMID {test_case['expected_pmid']} が見つかりました！")

            # 期待されるPMIDが見つからなかった場合
            if test_case['expected_pmid']:
                found_pmids = [p['pmid'] for p in evidence['papers']]
                if test_case['expected_pmid'] not in found_pmids:
                    print(f"\n  ⚠️  期待されたPMID {test_case['expected_pmid']} がトップ10に含まれていません")
                    print(f"      見つかったPMIDs: {', '.join(found_pmids)}")
        else:
            print(f"\n⚠️  検索結果なし（status: {evidence['status']}）")

    print("\n" + "=" * 80)
    print("テスト完了")
    print("=" * 80)


def test_single_question():
    """単一の質問でテスト（デバッグ用）"""

    client = PubMedClient()
    service = EvidenceService(client, max_papers=10)

    question = '経口のセマグルチドと注射のセマグルチドでは体重減少効果に違いはありますか'

    print("=" * 80)
    print("単一質問テスト")
    print("=" * 80)
    print(f"\n質問: {question}\n")

    # クエリ変換のみテスト
    query = service._reformulate_query(question)
    print(f"変換後のクエリ: {query}\n")

    # PubMed検索を実行
    print("PubMed検索中...")
    evidence = service.retrieve_evidence(question, max_papers=10)

    print(f"\n検索クエリ: {evidence['search_query']}")
    print(f"該当論文数: {evidence['total_found']}件")
    print(f"取得論文数: {len(evidence['papers'])}件\n")

    if evidence['papers']:
        print("取得した論文:")
        for i, paper in enumerate(evidence['papers'], 1):
            print(f"\n[{i}] PMID: {paper['pmid']}")
            print(f"    Title: {paper['title']}")
            print(f"    Journal: {paper['journal']} ({paper['pubdate']})")

            # PMID 37385278 が含まれているか確認
            if paper['pmid'] == '37385278':
                print(f"    ✅ 目標のPMID 37385278（OASIS-1試験）が見つかりました！")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--single':
        test_single_question()
    else:
        test_query_reformulation()
