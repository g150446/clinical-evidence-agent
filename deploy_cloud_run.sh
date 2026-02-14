#!/bin/bash
# Cloud Run デプロイスクリプト - Clinical Evidence Agent Backend
# フルマネージドAPI統合版（OpenRouter + HF Dedicated Endpoint）

set -e

# プロジェクト設定
PROJECT_ID="fit-authority-209603"
SERVICE_NAME="clinical-evidence-backend"
REGION="asia-northeast1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Cloud Run設定
MEMORY="256Mi"
CPU="1"
TIMEOUT="600s"  # 10分に延長（HF Endpoint cold start対策）
MAX_INSTANCES="10"
MIN_INSTANCES="0"

echo "========================================="
echo "Cloud Run Deployment - Backend API"
echo "========================================="
echo "Project: ${PROJECT_ID}"
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo ""

# 環境変数をチェック
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠ Warning: OPENROUTER_API_KEY not set"
fi

if [ -z "$SAPBERT_ENDPOINT" ]; then
    echo "⚠ Warning: SAPBERT_ENDPOINT not set"
fi

if [ -z "$HF_TOKEN" ]; then
    echo "⚠ Warning: HF_TOKEN not set"
fi

echo ""
read -p "環境変数を.envから読み込みますか？ (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f .env ]; then
        echo "Loading .env file..."
        export $(grep -v '^#' .env | xargs)
        echo "✓ Environment variables loaded"
    else
        echo "✗ .env file not found"
        exit 1
    fi
fi

echo ""
echo "Step 1: Building Docker image..."
echo "-----------------------------------"
gcloud builds submit --tag ${IMAGE_NAME} .

echo ""
echo "Step 2: Deploying to Cloud Run..."
echo "-----------------------------------"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --memory ${MEMORY} \
    --cpu ${CPU} \
    --timeout ${TIMEOUT} \
    --max-instances ${MAX_INSTANCES} \
    --min-instances ${MIN_INSTANCES} \
    --allow-unauthenticated \
    --set-env-vars "\
QDRANT_CLOUD_ENDPOINT=${QDRANT_CLOUD_ENDPOINT},\
QDRANT_CLOUD_API_KEY=${QDRANT_CLOUD_API_KEY},\
OPENROUTER_API_KEY=${OPENROUTER_API_KEY},\
SAPBERT_ENDPOINT=${SAPBERT_ENDPOINT},\
HF_TOKEN=${HF_TOKEN},\
MEDGEMMA_CLOUD_ENDPOINT=${MEDGEMMA_CLOUD_ENDPOINT},\
NCBI_API_KEY=${NCBI_API_KEY:-},\
NCBI_EMAIL=${NCBI_EMAIL:-}" \
    --project ${PROJECT_ID}

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="

# サービスURLを取得
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --platform managed \
    --format 'value(status.url)' \
    --project ${PROJECT_ID})

echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Testing endpoints:"
echo "  - Health: ${SERVICE_URL}/api/status"
echo "  - Query:  ${SERVICE_URL}/api/query"
echo ""

read -p "ヘルスチェックを実行しますか？ (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Testing /api/status..."
    curl -s "${SERVICE_URL}/api/status" | python3 -m json.tool
    echo ""
fi

echo ""
echo "デプロイ完了！"
echo ""
echo "次のステップ:"
echo "1. フロントエンドの環境変数を更新:"
echo "   BACKEND_URL=${SERVICE_URL}"
echo ""
echo "2. エンドツーエンドテスト:"
echo "   curl -X POST ${SERVICE_URL}/api/query \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"query\": \"Does semaglutide reduce weight?\", \"mode\": \"rag\"}'"
