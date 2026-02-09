#!/usr/bin/env python3
"""
統合テストスクリプト
PubMed検索からエビデンス取得までの全フローをテスト
"""

from pubmed_client import PubMedClient
from evidence_service import EvidenceService, build_evidence_prompt


def test_full_workflow():
    """完全なワークフローのテスト"""

    print("\n" + "="*70)
    print("PubMed Evidence Integration - 統合テスト")
    print("="*70 + "\n")

    # 1. PubMedClientの初期化
    print("1. PubMedClient初期化...")
    client = PubMedClient()
    print("   ✓ 初期化成功\n")

    # 2. EvidenceServiceの初期化
    print("2. EvidenceService初期化...")
    evidence_service = EvidenceService(client, max_papers=3)
    print("   ✓ 初期化成功\n")

    # 3. テストクエリ
    test_questions = [
        "What is metformin used for?",
        "What are the symptoms of type 2 diabetes?",
        "How is hypertension treated?"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*70}")
        print(f"テスト {i}/{len(test_questions)}: {question}")
        print("="*70 + "\n")

        # エビデンス検索
        print("🔍 PubMed検索中...")
        evidence = evidence_service.retrieve_evidence(question, max_papers=3)

        # 結果表示
        print(f"\nステータス: {evidence['status']}")
        print(f"検索クエリ: {evidence['search_query']}")
        print(f"総該当件数: {evidence['total_found']:,}件")
        print(f"取得論文数: {len(evidence['papers'])}件")

        if evidence['papers']:
            print("\n📄 取得した論文:")
            for j, paper in enumerate(evidence['papers'], 1):
                print(f"\n[{j}] {paper['title'][:80]}...")
                print(f"    著者: {', '.join(paper['authors'][:3])}")
                print(f"    雑誌: {paper['journal']}")
                print(f"    PMID: {paper['pmid']}")
                print(f"    要約の長さ: {len(paper['abstract'])} 文字")

            # プロンプト生成のテスト
            print("\n📝 MedGemma用プロンプト生成...")
            prompt = build_evidence_prompt(question, evidence['formatted_context'])
            print(f"   プロンプトの長さ: {len(prompt)} 文字")
            print(f"   エビデンス部分: {len(evidence['formatted_context'])} 文字")

            # プロンプトのプレビュー
            print("\n💬 プロンプトのプレビュー:")
            print("-" * 70)
            preview_lines = prompt.split('\n')[:15]
            for line in preview_lines:
                print(line)
            if len(prompt.split('\n')) > 15:
                print("...")
            print("-" * 70)
        else:
            print("\n⚠️ 論文が取得できませんでした")

    print("\n" + "="*70)
    print("✅ 統合テスト完了")
    print("="*70)
    print("\n次のステップ:")
    print("1. ✅ PubMed API統合 - 完了")
    print("2. ✅ 要約全文取得 - 完了")
    print("3. ✅ エビデンスサービス - 完了")
    print("4. 🔄 MedGemmaとの統合テスト（MedGemmaを起動して実行）")
    print("\nMedGemmaとの統合テストを実行するには:")
    print("  python3 medgemma_test.py --test")
    print("\n対話モードで使用するには:")
    print("  python3 medgemma_test.py")
    print()


if __name__ == "__main__":
    try:
        test_full_workflow()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
