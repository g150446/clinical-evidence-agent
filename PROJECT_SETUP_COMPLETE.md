# MedGemma Project Setup - Complete ✅

## 成功事項

### 1. NCBI API Key 取得完了 ✅

**API Key:** `20b0c933e2b69aea8adf1a4a962035de9809`  
**Email:** `g150446@gmail.com`

- ✅ NCBIアカウント作成/ログイン完了
- ✅ APIキー生成成功
- ✅ `.env`ファイルに保存済み
- ✅ レート制限: 10 requests/second (APIキーありの場合)

### 2. プロジェクトファイル作成完了 ✅

作成済みファイル:
- `.env` - APIキーと設定情報
- `pubmed_test.py` - 基本的なテストコード
- `pubmed_api_test.py` - 完全版テストコード（APIキー対応）

### 3. 必要なパッケージ

```bash
pip install requests biopython python-dotenv --break-system-packages
```

すでにインストール済み ✅

## 現在の問題点

### ネットワーク制限

この環境からは `eutils.ncbi.nlm.nih.gov` への直接アクセスがブロックされています：

```
ProxyError: Unable to connect to proxy
403 Forbidden
```

## 解決策

### Option A: Google Colab で開発（推奨）

Google Colab ならネットワーク制限がありません：

1. Google Colab を開く: https://colab.research.google.com/
2. 新しいノートブックを作成
3. 以下のコードを実行:

```python
# セットアップ
!pip install requests python-dotenv

# APIキーを設定
import os
os.environ['NCBI_API_KEY'] = '20b0c933e2b69aea8adf1a4a962035de9809'
os.environ['NCBI_EMAIL'] = 'g150446@gmail.com'

# テストコード
import requests
import time

def test_pubmed_api():
    """PubMed API 動作確認"""
    response = requests.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
        params={
            'db': 'pubmed',
            'term': 'diabetes treatment Japan 2024',
            'retmax': 5,
            'retmode': 'json',
            'email': os.environ['NCBI_EMAIL'],
            'api_key': os.environ['NCBI_API_KEY']
        }
    )
    
    result = response.json()
    pmids = result['esearchresult']['idlist']
    count = result['esearchresult']['count']
    
    print(f"✅ PubMed API テスト成功!")
    print(f"総件数: {count} 件")
    print(f"取得: {len(pmids)} 件")
    print(f"PMIDs: {pmids}")
    
    return pmids

# 実行
pmids = test_pubmed_api()
```

### Option B: ローカル環境で開発

自分のPCで開発する場合：

```bash
# プロジェクトディレクトリを作成
mkdir medgemma-project
cd medgemma-project

# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# パッケージをインストール
pip install requests python-dotenv biopython

# .envファイルを作成
cat > .env << 'EOF'
NCBI_API_KEY=20b0c933e2b69aea8adf1a4a962035de9809
NCBI_EMAIL=g150446@gmail.com
EOF
```

その後、`pubmed_api_test.py` をコピーして実行。

### Option C: Kaggle Notebook で開発

Kaggle でも制限なしでアクセス可能：

1. https://www.kaggle.com/ にアクセス
2. "Create" → "New Notebook"
3. Google Colab と同じコードを実行

## 次のステップ（優先順）

### Phase 1: PubMed API 統合の完成（今週中）

1. **別環境でAPIテスト実行** ← 今ここ
   - Google Colab or ローカル環境
   - API動作確認
   - サンプルクエリのテスト

2. **PubMed API ラッパークラスの完成**
   - 検索機能
   - サマリー取得
   - 抄録取得
   - キャッシング機構

3. **基本的なWeb UI作成**
   - FastAPI or Flask
   - シンプルな検索フォーム
   - 結果表示

### Phase 2: MedGemma 統合（来週）

1. **MedGemmaモデルのセットアップ**
   - Hugging Face からダウンロード
   - ローカルでの動作確認
   - プロンプトエンジニアリング

2. **Evidence Synthesis パイプライン**
   - PubMed検索 → 論文取得 → MedGemma処理
   - 引用情報の付加
   - 回答生成

3. **デモの作成**
   - 実際の医療質問で動作確認
   - スクリーンショット/動画撮影

### Phase 3: ハッカソン準備（2週目）

1. **Google Cloud へのデプロイ**
   - Cloud Run or App Engine
   - デモ環境の構築

2. **ドキュメント作成**
   - README.md
   - デモ動画（日本語）
   - Zenn記事の下書き

3. **最終調整**
   - バグ修正
   - パフォーマンス改善
   - UI/UX 調整

## 重要な技術情報

### PubMed E-utilities API

**Base URL:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

**主要エンドポイント:**
- `esearch.fcgi` - 検索
- `esummary.fcgi` - サマリー取得
- `efetch.fcgi` - 詳細情報取得

**レート制限:**
- APIキーなし: 3 requests/second
- APIキーあり: 10 requests/second ✅

**パラメータ:**
- `db=pubmed` - データベース指定
- `term=...` - 検索クエリ
- `retmax=N` - 最大取得件数
- `retmode=json` - JSON形式で取得
- `api_key=...` - APIキー
- `email=...` - メールアドレス

### MedGemma モデル

**モデル選択肢:**
- `google/medgemma-2b` - 最小、高速
- `google/medgemma-7b` - 推奨バランス
- `google/medgemma-27b` - 最高品質、要GPU

**ハッカソン用推奨:** 2b または 7b

## コード例

### 1. 基本的な検索

```python
import requests
import os

def search_pubmed(query: str, max_results: int = 10):
    """PubMed検索"""
    response = requests.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
        params={
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'email': os.getenv('NCBI_EMAIL'),
            'api_key': os.getenv('NCBI_API_KEY')
        }
    )
    
    result = response.json()
    return result['esearchresult']['idlist']

# 使用例
pmids = search_pubmed('diabetes treatment Japan', max_results=5)
print(f"Found {len(pmids)} papers")
```

### 2. サマリー取得

```python
def fetch_summaries(pmids: list):
    """論文サマリー取得"""
    response = requests.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
        params={
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'json',
            'email': os.getenv('NCBI_EMAIL'),
            'api_key': os.getenv('NCBI_API_KEY')
        }
    )
    
    result = response.json()
    papers = []
    
    for pmid in pmids:
        if pmid in result['result']:
            paper = result['result'][pmid]
            papers.append({
                'pmid': pmid,
                'title': paper.get('title', ''),
                'authors': [a['name'] for a in paper.get('authors', [])],
                'pubdate': paper.get('pubdate', ''),
                'source': paper.get('source', '')
            })
    
    return papers

# 使用例
pmids = search_pubmed('diabetes treatment')
papers = fetch_summaries(pmids[:5])

for paper in papers:
    print(f"Title: {paper['title']}")
    print(f"Authors: {', '.join(paper['authors'][:3])}")
    print(f"Journal: {paper['source']}")
    print(f"URL: https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/")
    print()
```

## 参考リンク

- **PubMed E-utilities Documentation:** https://www.ncbi.nlm.nih.gov/books/NBK25501/
- **MedGemma Information:** https://developers.google.com/health-ai-developer-foundations
- **Japan Hackathon:** https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol4
- **MedGemma Challenge:** https://www.kaggle.com/competitions/med-gemma-impact-challenge

## 連絡先情報

**NCBI Account:**
- Email: g150446@gmail.com
- Username: g150446@gmail.com
- API Key: 20b0c933e2b69aea8adf1a4a962035de9809

## セキュリティ注意事項

⚠️ **APIキーの管理:**
- `.env` ファイルは絶対に Git にコミットしない
- `.gitignore` に `.env` を追加する
- 公開リポジトリでは環境変数として設定

```bash
# .gitignore に追加
echo ".env" >> .gitignore
```

---

## ステータスサマリー

| タスク | 状態 | 備考 |
|--------|------|------|
| NCBIアカウント作成 | ✅ 完了 | g150446@gmail.com |
| APIキー取得 | ✅ 完了 | 10 req/sec |
| 開発環境セットアップ | ⚠️ 一部完了 | ネットワーク制限あり |
| PubMed APIテスト | 🔄 進行中 | 別環境で実行予定 |
| MedGemmaセットアップ | ⏳ 未着手 | APIテスト後 |
| Web UI 作成 | ⏳ 未着手 | |
| デプロイ準備 | ⏳ 未着手 | Google Cloud |
| ハッカソン提出 | ⏳ 未着手 | 2週間後 |

---

**最終更新:** 2026-01-30
**作成者:** MedGemma Project Team
**プロジェクトスタート:** 2週間でMVP完成を目指す！
