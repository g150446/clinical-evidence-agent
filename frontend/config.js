// Backend URL設定
// Cloud Run環境変数が設定されている場合、それを優先
// そうでなければ、Tailscale Funnel URLを使用（ハッカソンデプロイ）
window.API_BASE_URL = window.API_BASE_URL || 'https://macbookair-g150446.taile24f86.ts.net';

// デプロイ環境で上書き可能
// Cloud Runデプロイ時に: --set-env-vars="API_BASE_URL=https://xxxx.ngrok-free.app"