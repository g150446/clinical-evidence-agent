"""
エビデンス検索サービス
医学的質問からPubMed論文を検索し、MedGemma用のコンテキストに変換
"""

import re
from typing import Dict, List
from pubmed_client import PubMedClient
from medical_terms_dict import get_medical_term


class EvidenceService:
    """エビデンス検索とフォーマットを担当するサービスクラス"""

    def __init__(self, pubmed_client: PubMedClient, max_papers: int = 10):
        """
        Args:
            pubmed_client: PubMedClientインスタンス
            max_papers: 取得する論文の最大数（デフォルト: 10）
        """
        self.pubmed_client = pubmed_client
        self.max_papers = max_papers

    def retrieve_evidence(self, question: str, max_papers: int = None) -> Dict:
        """
        質問に基づいてPubMedからエビデンスを検索

        Args:
            question: 医学的質問
            max_papers: 取得する論文数（Noneの場合はデフォルト値を使用）

        Returns:
            エビデンス情報を含む辞書:
            {
                'papers': List[Dict],           # 論文情報のリスト
                'formatted_context': str,       # MedGemma用の整形済みテキスト
                'search_query': str,            # 実際の検索クエリ
                'total_found': int,             # 該当論文総数
                'status': str                   # 'success'/'no_results'/'error'
            }
        """
        if max_papers is None:
            max_papers = self.max_papers

        try:
            # 1. 質問を検索クエリに変換
            search_query = self._reformulate_query(question)

            # 2. PubMed検索を実行
            search_result = self.pubmed_client.search(search_query, max_results=max_papers)
            pmids = search_result['pmids']
            total_found = search_result['count']

            # 検索結果がない場合
            if not pmids:
                return {
                    'papers': [],
                    'formatted_context': '',
                    'search_query': search_query,
                    'total_found': 0,
                    'status': 'no_results'
                }

            # 3. 要約全文を取得
            papers = self.pubmed_client.fetch_abstracts(pmids)

            # 取得失敗時の処理
            if not papers:
                return {
                    'papers': [],
                    'formatted_context': '',
                    'search_query': search_query,
                    'total_found': total_found,
                    'status': 'error'
                }

            # 4. MedGemma用にフォーマット
            formatted_context = self._format_evidence_context(papers)

            return {
                'papers': papers,
                'formatted_context': formatted_context,
                'search_query': search_query,
                'total_found': total_found,
                'status': 'success'
            }

        except Exception as e:
            print(f"⚠️ エビデンス検索エラー: {e}")
            return {
                'papers': [],
                'formatted_context': '',
                'search_query': '',
                'total_found': 0,
                'status': 'error'
            }

    def _reformulate_query(self, question: str) -> str:
        """
        質問文をPubMed検索クエリに変換（改善版）

        処理フロー:
        1. 言語検出
        2. 日本語の場合: 医学用語を英語に変換
        3. 不要な語句を削除
        4. PubMed最適化

        Args:
            question: ユーザーの質問

        Returns:
            PubMed検索用のクエリ文字列
        """
        # ステップ1: 言語検出（簡易版）
        is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', question))

        if is_japanese:
            # ステップ2: 日本語医学用語を英語に変換
            query_parts = []

            # 複合語を優先的にマッチさせるため、最長一致法を使用
            # まず、複合語（長い用語）から検索し、マッチした部分をスキップ
            remaining_text = question
            position = 0

            while position < len(remaining_text):
                # 現在位置から最長の医学用語を探す
                matched = False
                max_length = min(20, len(remaining_text) - position)  # 最大20文字まで

                # 長い語から順に試す
                for length in range(max_length, 0, -1):
                    substring = remaining_text[position:position + length]

                    # 医学用語辞書で検索
                    english_term = get_medical_term(substring)

                    if english_term:
                        # OR演算子を含む用語はそのまま追加せず、最初の単語のみ使用
                        if ' OR ' in english_term:
                            first_term = english_term.split(' OR ')[0]
                            query_parts.append(first_term)
                        else:
                            query_parts.append(english_term)

                        position += length
                        matched = True
                        break

                if not matched:
                    # マッチしない場合、1文字進める
                    char = remaining_text[position]

                    # カタカナの場合は単語として抽出
                    if re.match(r'[\u30A0-\u30FF]', char):
                        # カタカナの連続を取得
                        katakana_word = ''
                        while position < len(remaining_text) and re.match(r'[\u30A0-\u30FF]', remaining_text[position]):
                            katakana_word += remaining_text[position]
                            position += 1

                        # ローマ字化
                        romanized = self._romanize_katakana(katakana_word)
                        if romanized:
                            query_parts.append(romanized)
                    else:
                        # その他の文字（助詞、句読点など）はスキップ
                        position += 1

            # 重複する単語を削除（例: "semaglutide"が2回出現する場合）
            unique_terms = []
            seen = set()
            for term in query_parts:
                # 小文字化して重複チェック
                term_lower = term.lower()
                if term_lower not in seen:
                    unique_terms.append(term)
                    seen.add(term_lower)

            # 特殊ケース: oral と injection が両方含まれている場合、injectionを削除
            # これは比較検索において、oral formulation の論文の方が関連性が高いため
            if 'oral' in seen and 'injection' in seen:
                unique_terms = [t for t in unique_terms if t.lower() != 'injection']

            query = ' '.join(unique_terms)
        else:
            # 英語の質問
            query = question

        # ステップ3: 不要な語句を削除
        query = re.sub(r'[?？。、,，]', '', query)
        query = re.sub(r'^(what|how|when|where|why|who|which)\s+', '', query, flags=re.IGNORECASE)
        query = re.sub(r'\b(is|are|the|a|an|in|on|at|to|for|of|with)\b', '', query, flags=re.IGNORECASE)

        # ステップ4: 複数スペースを1つに
        query = re.sub(r'\s+', ' ', query).strip()

        return query

    def _romanize_katakana(self, katakana: str) -> str:
        """
        カタカナを簡易的にローマ字化（主要な薬物名用）

        完璧な変換ではないが、セマグルチド→semaglutide のような
        近似的な変換を試みる

        Args:
            katakana: カタカナ文字列

        Returns:
            ローマ字化された文字列
        """
        # 基本的なカタカナ→ローマ字マッピング
        katakana_map = {
            'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
            'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
            'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
            'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
            'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
            'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
            'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
            'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
            'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
            'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n',
            'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
            'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
            'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
            'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
            'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
            'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo',
            'ー': '', 'ッ': '',  # 長音符と促音は削除
        }

        result = ''
        for char in katakana:
            result += katakana_map.get(char, char.lower())

        return result

    def _format_evidence_context(self, papers: List[Dict]) -> str:
        """
        論文情報をMedGemmaプロンプト用にフォーマット

        Args:
            papers: 論文情報のリスト

        Returns:
            整形済みのテキスト
        """
        formatted_parts = []

        for i, paper in enumerate(papers, 1):
            # 著者リスト
            authors_str = ', '.join(paper['authors']) if paper['authors'] else 'Unknown authors'
            if len(paper['authors']) > 3:
                authors_str += ', et al.'

            # 論文情報をフォーマット
            paper_text = f"""[{i}] Title: {paper['title']}
    Authors: {authors_str}
    Journal: {paper['journal']} ({paper['pubdate']})
    Abstract: {paper['abstract']}
    PMID: {paper['pmid']}
"""
            if paper.get('doi'):
                paper_text += f"    DOI: {paper['doi']}\n"

            formatted_parts.append(paper_text)

        return '\n'.join(formatted_parts)


def build_evidence_prompt(question: str, evidence_context: str) -> str:
    """
    エビデンスを含むMedGemma用プロンプトを構築

    Args:
        question: 医学的質問
        evidence_context: フォーマット済みのエビデンステキスト

    Returns:
        完全なプロンプト文字列
    """
    prompt = f"""You are a medical AI assistant. Answer the following medical question based on the scientific evidence provided below.

MEDICAL QUESTION:
{question}

SCIENTIFIC EVIDENCE FROM PUBMED:
{evidence_context}

INSTRUCTIONS:
1. Answer based primarily on the evidence provided above
2. Cite sources using [1], [2], etc. (you have access to multiple papers)
3. Be concise and focus on the most important findings
4. Limit your answer to 3-5 key points maximum
5. Synthesize findings from multiple papers when they agree
6. If evidence is insufficient, clearly state what is known and unknown
7. Use clear, professional medical language

YOUR EVIDENCE-BASED ANSWER:"""

    return prompt
