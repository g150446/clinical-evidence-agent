#!/usr/bin/env python3
"""
肥満治療論文 検索・選別・ダウンロードスクリプト
指定された分野（lifestyle, pharmacologic, surgical）のサブセクションごとに
PubMed検索を行い、LLMで有用性を判定して階層ディレクトリに保存します。

使い方:
    python scripts/fetch_paper_details.py [分野...] [オプション]

引数:
    分野: lifestye | pharmacologic | surgical (省略時は全て実行)

オプション:
    -n, --max-results INT: ダウンロードする論文数 (デフォルト: 15)

使用例:
    # pharmacologicのみ実行
    python scripts/fetch_paper_details.py pharmacologic

    # lifestyleとsurgicalを各20件ずつ
    python scripts/fetch_paper_details.py lifestyle surgical --max-results 20

    # 全カテゴリをデフォルト設定で実行
    python scripts/fetch_paper_details.py
"""

import requests
import json
import time
import os
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from openai import OpenAI

# ==========================================
# 設定 & 定義
# ==========================================

# OpenRouter / LLM設定
LLM_MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# PubMed API URL
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# 分野とサブセクション、検索クエリの定義
# 期間は過去5-10年、主要な論文タイプに絞る設定を含めています
SEARCH_CONFIG = {
    "lifestyle": {
        "dietary_interventions": '("Obesity"[Mesh]) AND ("Diet, Reducing"[Mesh] OR "Caloric Restriction"[Mesh] OR "Intermittent Fasting") AND ("Review"[Publication Type] OR "Clinical Trial"[Publication Type]) AND ("2015"[Date - Publication] : "3000"[Date - Publication])',
        "physical_activity": '("Obesity"[Mesh]) AND ("Exercise"[Mesh] OR "Physical Exertion"[Mesh]) AND ("Meta-Analysis"[Publication Type] OR "Systematic Review"[Publication Type]) AND ("2015"[Date - Publication] : "3000"[Date - Publication])',
        "behavioral_therapy": '("Obesity"[Mesh]) AND ("Cognitive Behavioral Therapy"[Mesh] OR "Behavior Therapy"[Mesh]) AND ("2015"[Date - Publication] : "3000"[Date - Publication])'
    },
    "pharmacologic": {
        "glp1_receptor_agonists": '("Obesity"[Mesh]) AND ("Semaglutide" OR "Liraglutide" OR "GLP-1 Receptor Agonists") AND ("Clinical Trial"[Publication Type] OR "Randomized Controlled Trial"[Publication Type]) AND ("2018"[Date - Publication] : "3000"[Date - Publication])',
        "novel_agents": '("Obesity"[Mesh]) AND ("Tirzepatide" OR "Retatrutide" OR "Orforglipron" OR "GIP") AND ("2020"[Date - Publication] : "3000"[Date - Publication])',
        "guidelines_and_reviews": '("Obesity/drug therapy"[Mesh]) AND ("Practice Guideline"[Publication Type] OR "Systematic Review"[Publication Type]) AND ("2020"[Date - Publication] : "3000"[Date - Publication])'
    },
    "surgical": {
        "procedures_and_outcomes": '("Obesity, Morbid/surgery"[Mesh]) AND ("Bariatric Surgery"[Mesh] OR "Gastric Bypass" OR "Sleeve Gastrectomy") AND ("Meta-Analysis"[Publication Type]) AND ("2015"[Date - Publication] : "3000"[Date - Publication])',
        "metabolic_effects": '("Bariatric Surgery"[Mesh]) AND ("Diabetes Mellitus, Type 2"[Mesh] OR "Remission Induction") AND ("Review"[Publication Type])',
        "complications_safety": '("Bariatric Surgery/adverse effects"[Mesh]) AND ("Postoperative Complications"[Mesh]) AND ("2015"[Date - Publication] : "3000"[Date - Publication])'
    }
}

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# ==========================================
# 関数定義
# ==========================================

def search_pubmed(query, max_results=20):
    """
    指定されたクエリでPubMedを検索し、PMIDリストを返す
    """
    params = {
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'retmode': 'json',
        'sort': 'relevance' # 関連度順
    }
    try:
        response = requests.get(ESEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('esearchresult', {}).get('idlist', [])
    except Exception as e:
        print(f"    ! 検索エラー: {e}")
        return []

def fetch_papers_details(pmids):
    """
    PMIDリストから論文詳細を取得 (EFetch)
    """
    if not pmids:
        return []
    
    # URL長対策のため、batchはここではなく呼び出し元で制御推奨だが、
    # 今回は max_results=20程度なので一括で処理
    papers = []
    params = {
        'db': 'pubmed',
        'id': ','.join(pmids),
        'retmode': 'xml'
    }
    
    try:
        response = requests.get(EFETCH_URL, params=params, timeout=60)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        for article in root.findall('.//PubmedArticle'):
            paper = parse_article_xml(article)
            if paper:
                papers.append(paper)
        return papers
    except Exception as e:
        print(f"    ! 詳細取得エラー: {e}")
        return []

def parse_article_xml(article_elem):
    """
    XMLパース処理
    """
    try:
        pmid = article_elem.find('.//PMID').text
        title = article_elem.find('.//ArticleTitle').text or "No Title"
        
        abstract_texts = article_elem.findall('.//Abstract/AbstractText')
        abstract = ' '.join([t.text for t in abstract_texts if t.text]) if abstract_texts else "No Abstract"
        
        journal = article_elem.find('.//Journal/Title').text or ""
        year_elem = article_elem.find('.//PubDate/Year')
        year = year_elem.text if year_elem is not None else "N/A"
        
        return {
            'pmid': pmid,
            'title': title,
            'abstract': abstract,
            'journal': journal,
            'year': year
        }
    except Exception:
        return None

def load_existing_papers(save_dir):
    """
    既存のpapers.jsonを読み込む
    """
    save_path = Path(save_dir) / 'papers.json'
    if save_path.exists():
        with open(save_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def filter_papers_with_llm(papers, category, subsection):
    """
    LLMを使用して、論文が該当サブセクションの学習資料として適切か判定
    """
    if not papers:
        return []

    print(f"    > LLM選別開始: {category}/{subsection} ({len(papers)}件)")

    candidates = [{"id": p['pmid'], "title": p['title'], "abstract": p['abstract'][:800]} for p in papers]

    system_prompt = f"""
    あなたは医学リサーチアシスタントです。
    カテゴリ「{category}」のサブセクション「{subsection}」に関する知識ベースを構築しています。
    入力された論文が、このテーマの学習資料として「高品質かつ関連性が高い」か判定してください。

    【判定基準】
    KEEP (true):
    - テーマに合致するガイドライン、RCT、メタ解析、重要レビュー。
    - 結論が明確で、臨床的意義があるもの。

    DISCARD (false):
    - テーマと関連が薄い。
    - 動物実験のみで臨床的示唆がない。
    - 抄録がなく内容不明。

    出力: JSON形式 {{"results": [{{"id": "PMID", "keep": true/false}}]}}
    """

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(candidates, ensure_ascii=False)}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )

        content = completion.choices[0].message.content
        if content is None:
            print(f"    ! LLMレスポンスなし")
            return papers

        result = json.loads(content)
        keep_map = {item['id']: item['keep'] for item in result.get('results', [])}

        filtered = [p for p in papers if keep_map.get(p['pmid'], False)]
        return filtered

    except Exception as e:
        print(f"    ! LLMエラー: {e}")
        return papers # エラー時は全件保存（安全策）

# ==========================================
# メイン処理
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Download Obesity Treatment Papers by Category")
    parser.add_argument('categories', nargs='*',
                        choices=['lifestyle', 'pharmacologic', 'surgical'],
                        help="対象とする分野を指定 (例: pharmacologic surgical)")
    parser.add_argument('--max-results', '-n', type=int, default=15,
                        help='ダウンロードする論文数 (デフォルト: 15)')

    args = parser.parse_args()
    
    # 引数がなければ全て実行
    target_categories = args.categories if args.categories else ['lifestyle', 'pharmacologic', 'surgical']

    if not OPENROUTER_API_KEY:
        print("エラー: OPENROUTER_API_KEY が設定されていません。")
        return

    print("=" * 60)
    print(f"処理対象分野: {', '.join(target_categories)}")
    print(f"ダウンロード件数: {args.max_results}件/サブセクション")
    print("=" * 60)

    total_saved = 0

    for category in target_categories:
        subsections = SEARCH_CONFIG[category]
        print(f"\n■ 分野: {category.upper()}")
        
        for subsection, query in subsections.items():
            print(f"  ├ サブセクション: {subsection}")

            # 1. 保存先ディレクトリ作成
            save_dir = Path(f'data/obesity/{category}/{subsection}')
            save_dir.mkdir(parents=True, exist_ok=True)

            # 2. 既存データの読み込み
            existing_papers = load_existing_papers(save_dir)
            existing_pmids = {p['pmid'] for p in existing_papers}

            # 3. 検索 (ESearch) - 既存分を含めて取得して重複を除外
            search_limit = args.max_results + len(existing_pmids)
            all_pmids = search_pubmed(query, max_results=search_limit)

            new_pmids = [pmid for pmid in all_pmids if pmid not in existing_pmids][:args.max_results]

            if not new_pmids:
                print(f"    -> 新規論文なし (既存{len(existing_papers)}件のみ)")
                total_saved += len(existing_papers)
                continue
            
            # 4. 詳細取得 (EFetch) - 新規PMIDのみ
            papers = fetch_papers_details(new_pmids)

            # 5. LLMフィルタリング（新規取得データのみ）
            valid_papers = filter_papers_with_llm(papers, category, subsection)

            # 6. マージして保存
            merged_papers = existing_papers + valid_papers
            save_path = save_dir / 'papers.json'

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(merged_papers, f, indent=2, ensure_ascii=False)

            print(f"    -> 保存完了: 既存 {len(existing_papers)} + 新規 {len(valid_papers)} = 総計 {len(merged_papers)}件 ({save_path})")
            total_saved += len(merged_papers)
            
            # API負荷軽減のための待機
            time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"全処理完了。合計 {total_saved} 件の論文をダウンロードしました。")
    print("=" * 60)

if __name__ == '__main__':
    main()