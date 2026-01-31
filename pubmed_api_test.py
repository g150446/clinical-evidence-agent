"""
PubMed E-utilities API テストプログラム (with API Key)
10 requests/second で動作
"""

import requests
import time
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class PubMedClient:
    """PubMed API クライアント"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def __init__(self, email: str = None, api_key: str = None):
        """
        Args:
            email: 連絡先メールアドレス（NCBI必須）
            api_key: APIキー（オプション）
        """
        self.email = email or os.getenv('NCBI_EMAIL')
        self.api_key = api_key or os.getenv('NCBI_API_KEY')
        
        # APIキーの有無でレート制限を調整
        if self.api_key:
            self.request_interval = 0.11  # 10 requests/second
            print(f"✅ APIキーあり: 10 requests/second")
        else:
            self.request_interval = 0.34  # 3 requests/second
            print(f"⚠️ APIキーなし: 3 requests/second")
        
        self.last_request_time = 0
        
    def _rate_limit(self):
        """レート制限を適用"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_time = time.time()
        
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """API リクエストを実行"""
        self._rate_limit()
        
        # 共通パラメータを追加
        params['email'] = self.email
        if self.api_key:
            params['api_key'] = self.api_key
        params['retmode'] = 'json'
        
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def search(self, query: str, max_results: int = 10) -> Dict:
        """
        PubMed検索を実行
        
        Args:
            query: 検索クエリ
            max_results: 最大取得件数
            
        Returns:
            検索結果（IDリストと件数情報）
        """
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'sort': 'relevance'
        }
        
        result = self._make_request('esearch.fcgi', params)
        search_result = result.get('esearchresult', {})
        
        return {
            'pmids': search_result.get('idlist', []),
            'count': int(search_result.get('count', 0)),
            'retmax': int(search_result.get('retmax', 0))
        }
    
    def fetch_summary(self, pmids: List[str]) -> List[Dict]:
        """
        論文のサマリー情報を取得
        
        Args:
            pmids: PubMed IDのリスト
            
        Returns:
            論文サマリーの辞書リスト
        """
        if not pmids:
            return []
        
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
        }
        
        result = self._make_request('esummary.fcgi', params)
        summaries = []
        
        result_data = result.get('result', {})
        for pmid in pmids:
            if pmid in result_data:
                paper = result_data[pmid]
                summaries.append({
                    'pmid': pmid,
                    'title': paper.get('title', 'No title'),
                    'authors': [f"{a.get('name', '')}" for a in paper.get('authors', [])[:3]],
                    'pubdate': paper.get('pubdate', 'Unknown'),
                    'source': paper.get('source', 'Unknown'),
                    'epubdate': paper.get('epubdate', ''),
                })
        
        return summaries


def test_basic_search():
    """基本的な検索テスト"""
    print("\n" + "=" * 70)
    print("テスト1: 基本的なPubMed検索")
    print("=" * 70)
    
    client = PubMedClient()
    
    # 検索実行
    query = "diabetes treatment Japan 2024"
    print(f"\n検索クエリ: {query}")
    print("検索中...")
    
    start_time = time.time()
    result = client.search(query, max_results=5)
    elapsed = time.time() - start_time
    
    pmids = result['pmids']
    total_count = result['count']
    
    print(f"\n総該当件数: {total_count:,} 件")
    print(f"取得件数: {len(pmids)} 件")
    print(f"処理時間: {elapsed:.2f} 秒")
    
    return pmids


def test_fetch_summaries(pmids: List[str]):
    """サマリー取得テスト"""
    print("\n" + "=" * 70)
    print("テスト2: 論文サマリー情報の取得")
    print("=" * 70)
    
    client = PubMedClient()
    
    print(f"\n{len(pmids)} 件の論文情報を取得中...")
    start_time = time.time()
    papers = client.fetch_summary(pmids)
    elapsed = time.time() - start_time
    
    print(f"処理時間: {elapsed:.2f} 秒")
    print(f"取得成功: {len(papers)} 件\n")
    
    for i, paper in enumerate(papers, 1):
        print(f"{i}. PMID: {paper['pmid']}")
        print(f"   Title: {paper['title'][:100]}...")
        print(f"   Authors: {', '.join(paper['authors'][:3])}")
        print(f"   Published: {paper['pubdate']}")
        print(f"   Journal: {paper['source']}")
        print(f"   URL: https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/")
        print()


def test_japanese_medical_queries():
    """日本語医療関連クエリのテスト"""
    print("\n" + "=" * 70)
    print("テスト3: 日本語医療用語での検索")
    print("=" * 70)
    
    client = PubMedClient()
    
    # 日本に関連する医療トピック
    queries = [
        "Japan diabetes prevalence",
        "Japanese population cardiovascular",
        "cancer treatment guidelines Japan"
    ]
    
    for query in queries:
        print(f"\n検索: {query}")
        result = client.search(query, max_results=3)
        pmids = result['pmids']
        total = result['count']
        
        print(f"  総該当件数: {total:,} 件")
        print(f"  取得: {len(pmids)} 件")
        if pmids:
            print(f"  例: https://pubmed.ncbi.nlm.nih.gov/{pmids[0]}/")


def test_speed_comparison():
    """速度比較テスト（APIキーあり vs なし）"""
    print("\n" + "=" * 70)
    print("テスト4: レート制限の確認")
    print("=" * 70)
    
    client = PubMedClient()
    
    print(f"\n5回連続検索のテスト...")
    queries = [
        "diabetes",
        "hypertension", 
        "cancer",
        "COVID-19",
        "heart disease"
    ]
    
    start_time = time.time()
    for query in queries:
        result = client.search(query, max_results=1)
        print(f"  {query}: {result['count']:,} 件")
    
    elapsed = time.time() - start_time
    print(f"\n合計処理時間: {elapsed:.2f} 秒")
    print(f"平均: {elapsed/5:.2f} 秒/クエリ")
    
    if client.api_key:
        print("\n✅ APIキーありの場合、さらに高速な検索が可能です！")
    else:
        print("\n⚠️ APIキーを取得すると、さらに高速化できます")


def main():
    """メインテスト実行"""
    print("\n" + "=" * 70)
    print("PubMed E-utilities API テストプログラム")
    print("=" * 70)
    
    # 環境変数の確認
    api_key = os.getenv('NCBI_API_KEY')
    email = os.getenv('NCBI_EMAIL')
    
    print(f"\nEmail: {email}")
    print(f"API Key: {'設定済み ✅' if api_key else '未設定 ⚠️'}")
    
    try:
        # テスト1: 基本検索
        pmids = test_basic_search()
        
        # テスト2: サマリー取得
        if pmids:
            test_fetch_summaries(pmids[:3])
        
        # テスト3: 日本語関連検索
        test_japanese_medical_queries()
        
        # テスト4: 速度テスト
        test_speed_comparison()
        
        print("\n" + "=" * 70)
        print("✅ すべてのテストが完了しました！")
        print("=" * 70)
        print("\n次のステップ:")
        print("1. ✅ PubMed API統合 - 完了")
        print("2. 🔄 MedGemmaモデルのセットアップ")
        print("3. 🔄 簡易Webインターフェースの作成")
        print("4. 🔄 キャッシング機構の実装")
        print("5. 🔄 Google Cloud へのデプロイ")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
