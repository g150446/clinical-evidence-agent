"""
PubMed E-utilities API クライアント
論文検索と要約取得機能を提供
"""

import requests
import time
import os
import xml.etree.ElementTree as ET
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
        else:
            self.request_interval = 0.34  # 3 requests/second

        self.last_request_time = 0

    def _rate_limit(self):
        """レート制限を適用"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict, retmode: str = 'json') -> requests.Response:
        """
        API リクエストを実行

        Args:
            endpoint: APIエンドポイント
            params: リクエストパラメータ
            retmode: レスポンス形式 ('json' or 'xml')

        Returns:
            レスポンスオブジェクト
        """
        self._rate_limit()

        # 共通パラメータを追加
        params['email'] = self.email
        if self.api_key:
            params['api_key'] = self.api_key
        if retmode:
            params['retmode'] = retmode

        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response

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

        response = self._make_request('esearch.fcgi', params)
        result = response.json()
        search_result = result.get('esearchresult', {})

        return {
            'pmids': search_result.get('idlist', []),
            'count': int(search_result.get('count', 0)),
            'retmax': int(search_result.get('retmax', 0)),
            'query': query
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

        response = self._make_request('esummary.fcgi', params)
        result = response.json()
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

    def fetch_abstracts(self, pmids: List[str]) -> List[Dict]:
        """
        論文の要約全文を取得

        Args:
            pmids: PubMed IDのリスト

        Returns:
            論文情報の辞書リスト（要約本文を含む）
            各辞書の構造:
            {
                'pmid': str,
                'title': str,
                'authors': List[str],
                'abstract': str,
                'journal': str,
                'pubdate': str,
                'doi': str (optional)
            }
        """
        if not pmids:
            return []

        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'rettype': 'abstract'
        }

        # XMLフォーマットでリクエスト
        response = self._make_request('efetch.fcgi', params, retmode='xml')

        # XMLをパース
        papers = []
        try:
            root = ET.fromstring(response.content)

            # 各論文を処理
            for article in root.findall('.//PubmedArticle'):
                paper_data = self._parse_pubmed_article(article)
                if paper_data:
                    papers.append(paper_data)

        except ET.ParseError as e:
            print(f"⚠️ XML解析エラー: {e}")
            return []

        return papers

    def _parse_pubmed_article(self, article: ET.Element) -> Optional[Dict]:
        """
        PubmedArticle XMLエレメントから論文情報を抽出

        Args:
            article: PubmedArticle XMLエレメント

        Returns:
            論文情報の辞書、またはNone
        """
        try:
            # PMID取得
            pmid_elem = article.find('.//PMID')
            if pmid_elem is None:
                return None
            pmid = pmid_elem.text

            # タイトル取得
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else 'No title'

            # 著者取得
            authors = []
            author_list = article.findall('.//Author')
            for author in author_list[:5]:  # 最大5人まで
                lastname = author.find('LastName')
                forename = author.find('ForeName')
                if lastname is not None:
                    name = lastname.text
                    if forename is not None:
                        name = f"{forename.text} {name}"
                    authors.append(name)

            # 要約取得（複数のAbstractTextを結合）
            abstract_parts = []
            abstract_texts = article.findall('.//AbstractText')
            for abstract_text in abstract_texts:
                # Label属性がある場合（例: BACKGROUND, METHODS, RESULTS）
                label = abstract_text.get('Label', '')
                text = abstract_text.text or ''

                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)

            abstract = ' '.join(abstract_parts) if abstract_parts else 'No abstract available'

            # 雑誌名取得
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else 'Unknown'

            # 出版日取得
            pubdate_year = article.find('.//PubDate/Year')
            pubdate_month = article.find('.//PubDate/Month')
            if pubdate_year is not None:
                pubdate = pubdate_year.text
                if pubdate_month is not None:
                    pubdate = f"{pubdate_month.text} {pubdate}"
            else:
                pubdate = 'Unknown'

            # DOI取得（オプション）
            doi = None
            for article_id in article.findall('.//ArticleId'):
                if article_id.get('IdType') == 'doi':
                    doi = article_id.text
                    break

            return {
                'pmid': pmid,
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'journal': journal,
                'pubdate': pubdate,
                'doi': doi
            }

        except Exception as e:
            print(f"⚠️ 論文解析エラー: {e}")
            return None
