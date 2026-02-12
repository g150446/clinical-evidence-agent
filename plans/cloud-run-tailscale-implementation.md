# Cloud Run + Tailscale 実装計画

## 概要

Google Cloud RunでFlaskサーバーを稼働し、Tailscaleを通じてmacbook-m1とmac-dev1上で稼働するMedGemmaとQdrantデータベースにアクセスする構成を実装します。

## アーキテクチャ

```
┌──────────────────────────────────────────────┐
│         Google Cloud Run (公開)           │
│                  Flask app.py             │
│  get_active_backend()                      │
│  ┌─────────────┐          ┌─────────────┐
│  │  Ollama     │          │   Qdrant    │
│  └──────┬──────┘          └──────┬──────┘
└─────────┼──────────────────────────┼────────┘
          │                      │
          └──────────┬───────────┘
                     │
              ┌──────▼───────────────────┐
              │      Tailscale (VPN)      │
              │  macbook-m1: 100.x.y.z   │
              │  mac-dev1: 100.x.y.z     │
              └───────────────────────────┘
                     │                      │
        ┌──────────▼──────┐      ┌───────▼──────────┐
        │  MacBook M1    │      │    Mac Dev 1      │
        │  (デフォルト)    │      │  (2/17以降)        │
        └─────────────────┘      └───────────────────┘
```

## バックエンド切り替えルール

| 期間 | アクティブバックエンド |
|------|-------------------|
| 〜2/16 | macbook-m1 |
| 2/17〜 | mac-dev1 |

手動オーバーライド: `ACTIVE_BACKEND` 環境変数で可能

## フェーズ別実装

### フェーズ1: MacBook M1でQdrantをHTTPモード起動

**目的**: ローカルのQdrantをHTTPサーバーとして起動

**ファイル**: `docker-compose.yml`（新規）

**実行コマンド**:
```bash
docker-compose up -d
```

---

### フェーズ2: Flaskアプリのバックエンド切り替え対応

**目的**: 環境変数に基づいてバックエンドを自動切り替え

**ファイル**: `app.py`（修正）

**追加機能**:
- `BACKENDS` マップの定義
- `get_active_backend()` 関数の実装
- `/api/status` エンドポイントの更新

---

### フェーズ3: search_qdrant.pyのHTTPモード対応

**目的**: Qdrant HTTP URLを動的に切り替え

**ファイル**: `scripts/search_qdrant.py`（修正）

**変更点**:
- 固定URLの削除
- `get_qdrant_url()` 関数の追加
- HTTPモードでのQdrantクライアント初期化

---

### フェーズ4: medgemma_query.pyのOllama URL対応

**目的**: Ollama HTTP URLを動的に切り替え

**ファイル**: `scripts/medgemma_query.py`（修正）

**変更点**:
- 固定URLの削除
- `get_ollama_url()` 関数の追加
- `query_ollama()` 関数での使用

---

### フェーズ5: Qdrantデータ移行スクリプト

**目的**: macbook-m1からmac-dev1へデータを移行

**ファイル**: `scripts/migrate_qdrant_data.py`（新規）

---

### フェーズ6: Dockerfile作成

**目的**: Flaskアプリ用のDockerイメージ定義

**ファイル**: `Dockerfile`（新規）

---

### フェーズ7: requirements.txt作成

**目的**: Python依存関係の定義

**ファイル**: `requirements.txt`（新規）

---

### フェーズ8: .gcloudignore作成

**目的**: デプロイ対象外ファイルの指定

**ファイル**: `.gcloudignore`（新規）

---

### フェーズ9: Google Cloudプロジェクト設定

**目的**: Cloud Runデプロイの準備

**実行コマンド**:
```bash
gcloud auth login
gcloud config set project fit-authority-209603
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com
```

---

### フェーズ10: Cloud Runデプロイ

**目的**: `gcloud run deploy --source .` でデプロイ

**実行コマンド**:
```bash
gcloud run deploy clinical-evidence-agent \
    --source . \
    --region asia-northeast1 \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --set-env-vars TAILNET_NAME=<your-tailnet-name> \
    --set-env-vars SWITCH_DATE=2025-02-17
```

---

## 環境変数

| 変数名 | 説明 | デフォルト値 | 必須 |
|--------|------|------------|------|
| `TAILNET_NAME` | Tailscaleネットワーク名 | - | ✅ |
| `SWITCH_DATE` | 自動切り替え日付 | 2025-02-17 | ❌ |
| `ACTIVE_BACKEND` | 手動オーバーライド | 未設定 | ❌ |

---

## 2月17日の切り替え手順

1. **Mac Dev 1でQdrantを起動**: `docker-compose up -d`
2. **データ移行**: `python3 scripts/migrate_qdrant_data.py --source http://macbook-m1.tailnet-name.ts.net:6333 --dest http://mac-dev1.tailnet-name.ts.net:6333`
3. **自動切り替え確認**: `curl https://<cloud-run-url>/api/status`

---

## 緊急時の手動切り替え

```bash
gcloud run services update clinical-evidence-agent \
  --region asia-northeast1 \
  --set-env-vars=ACTIVE_BACKEND=macbook-m1
```
