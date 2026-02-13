// Backend URL設定
window.API_BASE_URL = window.API_BASE_URL || 'http://localhost:8080';

// デプロイ環境で上書き可能
// Cloud Runデプロイ時に: --set-env-vars="API_BASE_URL=https://xxxx.ngrok-free.app"