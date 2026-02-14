#!/bin/bash
# Cloud Run 環境変数更新スクリプト
# 既存サービスの環境変数のみを更新（再ビルド不要）

set -e

PROJECT_ID="fit-authority-209603"
SERVICE_NAME="clinical-evidence-backend"
REGION="asia-northeast1"

echo "========================================="
echo "Cloud Run Environment Variables Update"
echo "========================================="
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo ""

# .envから環境変数をロード
if [ -f .env ]; then
    echo "Loading .env file..."
    export $(grep -v '^#' .env | xargs)
    echo "✓ Environment variables loaded"
else
    echo "✗ .env file not found"
    exit 1
fi

echo ""
echo "環境変数を更新します..."
echo ""

gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --update-env-vars "\
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
echo "✓ 環境変数の更新が完了しました"
echo ""

# 現在の環境変数を確認
echo "現在の環境変数:"
gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(spec.template.spec.containers[0].env)' \
    --project ${PROJECT_ID}
