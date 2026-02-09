#!/usr/bin/env python3
"""
既存のpapers.jsonを読み込み、Full Text (PMC) を追加取得するスクリプト
scriptsフォルダに配置して実行することを想定しています。
.envファイルからNCBI_API_KEYを読み込みます。
"""

import requests
import json
import time
import os
from pathlib import Path
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

# ==========================================
# パス設定 & .env読み込み
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = BASE_DIR / "data" / "obesity"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)
NCBI_API_KEY = os.getenv("NCBI_API_KEY")

# ==========================================
# API設定
# ==========================================
ID_CONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EMAIL = "your_email@example.com" 

SLEEP_TIME = 0.15 if NCBI_API_KEY else 0.4

# ==========================================
# 関数
# ==========================================

def get_pmcids_from_pmids(pmids):
    """PMIDリストを一括でPMCIDに変換"""
    if not pmids:
        return {}
    
    # 全て文字列に変換して結合
    pmids_str = ','.join([str(p) for p in pmids])
    
    params = {
        'ids': pmids_str,
        'format': 'json',
        'tool': 'python_script',
        'email': EMAIL
    }
    
    if NCBI_API_KEY:
        params['api_key'] = NCBI_API_KEY
    
    try:
        response = requests.get(ID_CONV_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        mapping = {}
        for record in data.get('records', []):
            if 'pmcid' in record:
                # 【重要】キーを必ず文字列(str)に変換して保存
                mapping[str(record['pmid'])] = record['pmcid']
        return mapping
    except Exception as e:
        print(f"    ! ID変換エラー: {e}")
        return {}

def fetch_full_text_xml(pmcid):
    """PMCIDからXMLを取得し、本文テキストを抽出"""
    params = {
        'db': 'pmc',
        'id': pmcid,
        'retmode': 'xml',
        'tool': 'python_script',
        'email': EMAIL
    }

    if NCBI_API_KEY:
        params['api_key'] = NCBI_API_KEY

    try:
        response = requests.get(EFETCH_URL, params=params, timeout=60)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        # 本文抽出ロジック強化
        # bodyタグだけでなく、記事全体から有用なテキストを探す
        full_text_parts = []
        
        # タイトル、アブストラクト以外の本文セクションを取得
        body_elems = root.findall('.//body')
        
        if not body_elems:
            # bodyがない場合でも、特定のタグ構造で取得できるか試行
            return None
        
        for body in body_elems:
            # itertextでタグを除去してテキスト化
            text = ''.join(body.itertext())
            full_text_parts.append(text)
            
        combined_text = "\n".join(full_text_parts)
        
        # 空っぽならNone
        if len(combined_text.strip()) < 50:
            return None
            
        return combined_text
        
    except Exception as e:
        return None

def process_json_file(file_path):
    """1つのJSONファイルを処理して更新"""
    try:
        rel_path = file_path.relative_to(BASE_DIR)
    except ValueError:
        rel_path = file_path
        
    print(f"処理中: {rel_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        papers = json.load(f)
    
    target_papers = [
        p for p in papers 
        if not p.get('has_full_text') and p.get('pmid')
    ]
    
    if not target_papers:
        print("  -> 更新対象なし")
        return

    # 1. PMID -> PMCID 変換
    pmids = [str(p['pmid']) for p in target_papers] # 文字列として抽出
    pmid_to_pmcid = get_pmcids_from_pmids(pmids)
    
    if not pmid_to_pmcid:
        print(f"  -> {len(pmids)}件中、PMCIDが見つかりませんでした")
        return

    print(f"  -> {len(pmids)}件中 {len(pmid_to_pmcid)}件のPMCIDを取得")
    
    # 2. Full Text 取得
    updated_count = 0
    for paper in papers:
        if paper.get('has_full_text'):
            continue
            
        # 【重要】辞書引きするときも必ずstrにする
        pmid = str(paper.get('pmid'))
        pmcid = pmid_to_pmcid.get(pmid)
        
        if pmcid:
            print(f"    - Downloading {pmcid} (PMID:{pmid})...")
            full_text = fetch_full_text_xml(pmcid)
            
            if full_text:
                paper['full_text'] = full_text
                paper['has_full_text'] = True
                paper['pmcid'] = pmcid
                updated_count += 1
            else:
                # PMC IDはあるが、XMLから本文が取れなかった（OAではない等）
                # print(f"      -> 取得失敗 (本文抽出不可)")
                paper['has_full_text'] = False
            
            time.sleep(SLEEP_TIME)
        else:
            paper['has_full_text'] = False 
            
    # 3. 保存
    if updated_count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        print(f"  -> 保存完了: {updated_count}件のFull Textを追加しました")
    else:
        print("  -> 追加できるFull Textはありませんでした (PMCIDはあるが本文取得失敗)")

# ==========================================
# メイン処理
# ==========================================

def main():
    if not DATA_ROOT.exists():
        print(f"エラー: データディレクトリが見つかりません: {DATA_ROOT}")
        return

    if NCBI_API_KEY:
        print(f"INFO: API Keyを確認しました。高速モードで実行します (Interval: {SLEEP_TIME}s)")
    else:
        print(f"INFO: API Keyが見つかりません。通常モードで実行します (Interval: {SLEEP_TIME}s)")
    
    json_files = list(DATA_ROOT.glob('**/*/papers.json'))
    
    if not json_files:
        print("papers.jsonファイルが見つかりませんでした。")
        return

    print(f"合計 {len(json_files)} 個のファイルが見つかりました。\n")
    
    for json_file in json_files:
        process_json_file(json_file)
        print("-" * 40)

if __name__ == '__main__':
    main()
