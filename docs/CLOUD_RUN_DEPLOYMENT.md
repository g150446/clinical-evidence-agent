# Cloud Run デプロイメントガイド

## 現在の状況

### 既存サービス
- **Frontend**: `clinical-evidence-frontend`
  - Region: `asia-northeast1`
  - URL: https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
  - Status: デプロイ済み（2026-02-13）

### 新規サービス（このデプロイ）
- **Backend**: `clinical-evidence-backend`
  - Region: `asia-northeast1`（フロントエンドと同じ）
  - Image: `gcr.io/fit-authority-209603/clinical-evidence-backend`
  - Memory: 256Mi
  - Timeout: 300s

---

## アーキテクチャ変更点

### 旧アーキテクチャ（Digital Ocean計画）
```
Cloud Run → Digital Ocean (Embedding Service) → Qdrant Cloud
```

### 新アーキテクチャ（フルマネージドAPI）
```
Cloud Run → OpenRouter API (E5) → Qdrant Cloud
         → HF Dedicated Endpoint (SapBERT)
         → HF Endpoint (MedGemma)
```

**変更理由**: Digital Oceanメモリ不足（2GB RAMでOOM Killed）

---

## デプロイ手順

### 方法1: 自動デプロイスクリプト（推奨）

```bash
# .envファイルから環境変数を読み込んでデプロイ
./deploy_cloud_run.sh
```

**実行内容**:
1. Docker imageビルド（Cloud Build使用）
2. Cloud Runデプロイ
3. 環境変数設定
4. ヘルスチェック実行

---

### 方法2: 手動デプロイ

#### Step 1: Docker Imageビルド

```bash
export PROJECT_ID="fit-authority-209603"
export SERVICE_NAME="clinical-evidence-backend"
export IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

gcloud builds submit --tag ${IMAGE_NAME} .
```

#### Step 2: Cloud Runデプロイ

```bash
# .envから環境変数をロード
export $(grep -v '^#' .env | xargs)

gcloud run deploy clinical-evidence-backend \
  --image gcr.io/fit-authority-209603/clinical-evidence-backend \
  --platform managed \
  --region asia-northeast1 \
  --memory 256Mi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --min-instances 0 \
  --allow-unauthenticated \
  --set-env-vars "\
QDRANT_CLOUD_ENDPOINT=${QDRANT_CLOUD_ENDPOINT},\
QDRANT_CLOUD_API_KEY=${QDRANT_CLOUD_API_KEY},\
OPENROUTER_API_KEY=${OPENROUTER_API_KEY},\
SAPBERT_ENDPOINT=${SAPBERT_ENDPOINT},\
HF_TOKEN=${HF_TOKEN},\
MEDGEMMA_CLOUD_ENDPOINT=${MEDGEMMA_CLOUD_ENDPOINT}" \
  --project fit-authority-209603
```

---

### 方法3: 環境変数のみ更新（再デプロイ不要）

コード変更なしで環境変数だけ更新する場合:

```bash
./update_env_vars.sh
```

または手動で:

```bash
export $(grep -v '^#' .env | xargs)

gcloud run services update clinical-evidence-backend \
  --region asia-northeast1 \
  --update-env-vars "\
QDRANT_CLOUD_ENDPOINT=${QDRANT_CLOUD_ENDPOINT},\
OPENROUTER_API_KEY=${OPENROUTER_API_KEY},\
SAPBERT_ENDPOINT=${SAPBERT_ENDPOINT},\
HF_TOKEN=${HF_TOKEN}" \
  --project fit-authority-209603
```

---

## 必要な環境変数

### 必須（.envに設定）

```bash
# Qdrant Cloud
QDRANT_CLOUD_ENDPOINT="https://b1b30e67-4045-43f9-ac3f-b869a16613ee.us-east4-0.gcp.cloud.qdrant.io"
QDRANT_CLOUD_API_KEY="<secret>"

# OpenRouter API (E5 embeddings)
OPENROUTER_API_KEY="sk-or-v1-..."

# HF Dedicated Endpoint (SapBERT embeddings)
SAPBERT_ENDPOINT="https://wpmws71x1qnvci7u.us-east-1.aws.endpoints.huggingface.cloud"
HF_TOKEN="hf_..."

# MedGemma Endpoint
MEDGEMMA_CLOUD_ENDPOINT="https://vx7ota6spdsefs63.us-east-1.aws.endpoints.huggingface.cloud"
```

### オプション

```bash
NCBI_API_KEY="<optional>"
NCBI_EMAIL="<optional>"
```

---

## デプロイ後の確認

### 1. ヘルスチェック

```bash
SERVICE_URL=$(gcloud run services describe clinical-evidence-backend \
  --region asia-northeast1 \
  --format 'value(status.url)' \
  --project fit-authority-209603)

curl -s ${SERVICE_URL}/api/status | jq .
```

**期待される出力**:
```json
{
  "status": "healthy",
  "qdrant": "connected",
  "embedding_apis": {
    "openrouter": "configured",
    "hf_dedicated": "configured"
  }
}
```

### 2. 検索テスト

```bash
curl -X POST ${SERVICE_URL}/api/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Does semaglutide reduce weight in obesity?",
    "mode": "rag"
  }' | jq .
```

### 3. ストリーミングテスト

```bash
curl -X POST ${SERVICE_URL}/api/query \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "query": "semaglutideの体重減少効果は？",
    "mode": "compare"
  }'
```

---

## トラブルシューティング

### エラー: "OPENROUTER_API_KEY not set"

```bash
# .envファイルを確認
cat .env | grep OPENROUTER

# 環境変数が正しく設定されているか確認
gcloud run services describe clinical-evidence-backend \
  --region asia-northeast1 \
  --format 'value(spec.template.spec.containers[0].env)'
```

### エラー: "Failed to generate E5 embedding"

OpenRouter APIキーの確認:
```bash
curl -X POST https://openrouter.ai/api/v1/embeddings \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "intfloat/multilingual-e5-large", "input": "test"}'
```

### エラー: "SapBERT endpoint loading"

HF Dedicated Endpointは初回起動に10-30秒かかります。リトライ機能が実装済みです。

---

## フロントエンド統合

Backend デプロイ後、Frontendの環境変数を更新:

```bash
# Backend URLを取得
BACKEND_URL=$(gcloud run services describe clinical-evidence-backend \
  --region asia-northeast1 \
  --format 'value(status.url)' \
  --project fit-authority-209603)

# Frontendを更新
gcloud run services update clinical-evidence-frontend \
  --region asia-northeast1 \
  --update-env-vars "BACKEND_URL=${BACKEND_URL}" \
  --project fit-authority-209603
```

---

## コスト見積もり

| サービス | 月額 |
|---------|------|
| Cloud Run Backend | 無料枠内 or ~$1-5 |
| OpenRouter API (E5) | ~$0.01/1000検索 |
| HF Dedicated (SapBERT) | $24/月（固定） |
| Qdrant Cloud | 無料枠内 |
| MedGemma Endpoint | 従量課金 |
| **合計** | **~$25-30/月** |

---

## 参考リンク

- [API統合サマリー](../.copilot/session-state/.../api_integration_summary.md)
- [アーキテクチャプラン](../.copilot/session-state/.../plan.md)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
