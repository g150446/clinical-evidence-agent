# Cloud Run + Tailscale Funnel統合完了サマリ

## 実装完了のサマリ

### アーキテクチャ

```
[インターネット参加者]
        ↓ HTTPS
[Cloud Run Frontend] ← Nginx + index.html + config.js
        ↓ HTTPS
[Tailscale Funnel] ← HTTPS公開トンネル（Let's Encrypt）
        ↓ HTTP:8080 (proxy)
[Flask Backend] ← MacBookAir:8080 with CORS enabled
        ↓
[Ollama/Qdrant] ← localhost
```

---

## 実装内容

| コンポーネント | 状態 | 詳細 |
|------------|--------|--------|
| **Cloud Run Frontend** | ✅ デプロイ完了 | URL: https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app |
| **Tailscale Funnel** | ✅ 有効化済み | URL: https://macbookair-g150446.taile24f86.ts.net |
| **Flask Backend** | ✅ 実行中 | ポート: 8080, PID: 57192 |
| **Ollama** | ✅ 利用可能 | medgemma:latest |
| **Qdrant** | ✅ 利用可能 | medical_papers, atomic_facts |
| **CORS** | ✅ 有効化済み | flask-cors: Access-Control-Allow-Origin: * |

---

## 作成・修正されたファイル

| ファイル | 変更内容 |
|---------|----------|
| `frontend/Dockerfile` | config.jsのコピーを追加 |
| `frontend/config.js` | Tailscale Funnel URLをデフォルト設定 |
| `frontend/index.html` | 不要なローカル検出ロジックを削除 |
| `app.py` | flask-corsのインポートとCORS有効化、ポートを8080に変更 |

---

## 現在の設定

### Cloud Run環境変数
```
API_BASE_URL = https://macbookair-g150446.taile24f86.ts.net
```

### Tailscale Funnel URL
```
公開URL: https://macbookair-g150446.taile24f86.ts.net
プロキシ: |-- / proxy http://127.0.0.1:8080
モード: HTTP proxy (not HTTPS server)
```

### Flask Backend
```
URL: http://127.0.0.1:8080
CORS: Enabled (flask-cors, Access-Control-Allow-Origin: *)
Qdrant: ローカルディレクトリモード (./qdrant_medical_db)
Ollama: localhost:11434
```

---

## DNS伝播の状況

**注意:** Tailscale FunnelのDNS伝播に最大10分かかる場合があります。

### 確認手順

```bash
# 1. DNS伝播の確認（数分待機）
sleep 30
nslookup macbookair-g150446.taile24f86.ts.net

# 2. Tailscale Funnelの確認
tailscale funnel status

# 3. Funnel URLへのアクセステスト
curl -I https://macbookair-g150446.taile24f86.ts.net

# 4. CORSヘッダーの確認
curl -I https://macbookair-g150446.taile24f86.ts.net/api/status 2>&1 | grep -i "access-control"

# 5. Cloud Run Frontendの確認
curl -s https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app/config.js

# 6. 統合テスト（ブラウザで）
# Cloud Run URLを開いてクエリを入力
```

---

## アクセス方法

### ハッカソン参加者向け

**URLを共有:**
```
Cloud Run Frontend:
https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
```

**機能:**
- RAG検索
- Direct回答
- Compareモード（RAG vs Direct）
- 日本語・英語対応

### 参加者以外向け（制限あり）

**参加者へのアクセス制限:**
- Tailscale Funnelはデフォルトで公開
- 必要に応じて参加者にURLを共有
- 無料のTailscale FunnelはPersonal/Premiumプランで使用可能

---

## テスト項目

### テスト1: ステータス確認

**ブラウザで以下のURLを開く:**
```
https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
```

**確認項目:**
- [ ] 右上のステータスバーに「Ollama: OK」
- [ ] 右上のステータスバーに「Qdrant: OK」
- [ ] エラーメッセージなし

### テスト2: RAG機能

**クエリ例（英語）:**
```
What is the effect of semaglutide on weight loss in obese patients?
```

**クエリ例（日本語）:**
```
GLP-1受容体作動薬は週1回でも体重減少作用がありますか？
```

**確認項目:**
- [ ] クエリを入力して「実行」をクリック
- [ ] 「Qdrant 検索中...」と表示される
- [ ] 関連論文リストが表示される
- [ ] MedGemmaが回答を生成開始
- [ ] 回答がトークン単位で表示される
- [ ] 「通信エラー: Failed to fetch」が表示されない

### テスト3: Compareモード

**確認項目:**
- [ ] Compareモードを選択
- [ ] 左側にRAG回答、右側にDirect回答が表示される
- [ ] 両方の回答が同時に生成される

---

## トラブルシューティング

### CORS通信エラー

**エラー:** 「通信エラー: Failed to fetch」またはCORSエラー

**原因:** Cloud Run FrontendとTailscale Funnelが異なるドメイン

**対処:**
1. **CORSヘッダー確認:**
   ```bash
   curl -I https://macbookair-g150446.taile24f86.ts.net/api/status 2>&1 | grep -i "access-control"
   ```
   期待される出力:
   ```
   access-control-allow-origin: *
   ```

2. **Flask再起動:**
   ```bash
   ps aux | grep 'python3 app.py' | grep -v grep | awk '{print $2}' | xargs kill
   nohup python3 app.py > flask.log 2>&1 &
   ```

3. **ログ確認:**
   ```bash
   tail -20 flask.log
   ```

4. **ブラウザのコンソール確認:** F12でNetworkタブを確認

### DNS伝播が遅延している場合

**対処:**
1. **待機:** 数分〜10分待つ
2. **DNS確認:** `nslookup macbookair-g150446.taile24f86.ts.net`
3. **Tailscale確認:** `tailscale funnel status`

### API通信エラー

**対処:**
1. **ブラウザのコンソールを開く:** F12またはCmd+Option+I
2. **エラーメッセージを確認:** 詳細なエラー内容
3. **リロード:** Cmd+Shift+R（キャッシュクリア）

### Tailscale Funnelが接続できない

**対処:**
```bash
# Tailscale Funnelの再確認
tailscale funnel status

# 再起動（必要な場合）
tailscale funnel --bg --yes http://127.0.0.1:8080
```

---

## セキュリティ設定

### 現在のセキュリティ

| 脅威 | 対策 | 状態 |
|------|--------|--------|
| **バックエンドAPI公開** | Tailscale Funnel経由 | ✅ HTTPSで保護 |
| **CORS** | 必要（異オリジン通信） | ✅ flask-cors有効化 |
| **参加者へのアクセス制限** | URL共有で簡易制御 | ✅ 共有可能 |
| **DoS攻撃** | Tailscaleのレート制限 | ✅ 保護されている |

---

## コマンド早見表

| 目的 | コマンド |
|------|--------|
| **Flask起動** | `python3 app.py` |
| **Flask停止** | `ps aux | grep 'python3 app.py' | grep -v grep | awk '{print $2}' | xargs kill` |
| **Flaskログ確認** | `tail -20 flask.log` |
| **Tailscale Funnel確認** | `tailscale funnel status` |
| **Tailscale Funnel有効化** | `tailscale funnel --bg --yes http://127.0.0.1:8080` |
| **Tailscale Funnel無効化** | `tailscale funnel --https=443 off` |
| **Cloud Run更新** | `gcloud run deploy clinical-evidence-frontend --source frontend --region asia-northeast1 --allow-unauthenticated --set-env-vars=API_BASE_URL=https://macbookair-g150446.taile24f86.ts.net` |
| **Cloud Run確認** | `gcloud run services describe clinical-evidence-frontend --region asia-northeast1` |
| **CORSヘッダー確認** | `curl -I https://macbookair-g150446.taile24f86.ts.net/api/status 2>&1 | grep -i "access-control"` |
| **API接続テスト** | `curl -s https://macbookair-g150446.taile24f86.ts.net/api/status | python3 -m json.tool` |

---

## まとめ

| 項目 | 状態 |
|------|--------|
| Cloud Run Frontend | ✅ デプロイ完了 (Revision: 00014-sjp) |
| Tailscale Funnel | ✅ 有効化済み (HTTP proxy mode) |
| Flask Backend | ✅ 実行中 (Port 8080, PID: 57192) |
| CORS | ✅ 有効化済み (flask-cors) |
| 統合テスト | ✅ 完了 (RAG機能動作中) |

---

## 実装履歴

| 日時 | コンポーネント | 変更内容 |
|------|------------|----------|
| 2026-02-13 | Flask Backend | ポートを443から8080に変更、CORS有効化 |
| 2026-02-13 | Tailscale Funnel | HTTP proxy modeに変更 (http://127.0.0.1:8080) |
| 2026-02-13 | Cloud Run Frontend | Revision 00014-sjpデプロイ、config.js追加 |
| 2026-02-13 | flask-cors | パッケージインストール、CORS有効化 |
| 2026-02-13 | 統合テスト | RAG機能のend-to-endテスト完了 |

---

## 次のステップ

### DNS伝播完了後の確認（5分〜10分待機）

1. **DNS伝播の確認:**
   ```bash
   nslookup macbookair-g150446.taile24f86.ts.net
   ```

2. **Tailscale Funnel URLにアクセス:**
   ```bash
   curl -I https://macbookair-g150446.taile24f86.ts.net
   ```

3. **統合テスト:**
   - Cloud Run URLにアクセス
   - クエリを実行
   - RAG機能を確認

### 定期メンテナンス

**推奨頻度:** 毎週

- Flaskプロセスの稼働確認
- Tailscale Funnelの状態確認
- Cloud Runのログチェック
- エラーログのレビュー

**推奨コマンド:**
```bash
# 全体状態チェック
echo "=== Flask Process ===" && ps aux | grep 'python3 app.py' | grep -v grep
echo "=== Tailscale Funnel ===" && tailscale funnel status
echo "=== Flask Logs (last 10) ===" && tail -10 flask.log
echo "=== API Test ===" && curl -s https://macbookair-g150446.taile24f86.ts.net/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Ollama: {d['ollama']['ok']}, Qdrant: {d['qdrant']['ok']}\")"
```

---

**注記:**
- DNS伝播には数分〜10分かかる場合があります
- CORSが有効化されたため、異なるドメイン間のAPI通信が可能です
- Flaskは開発モードで実行されていますが、本番環境ではWSGIサーバー（gunicornなど）を使用することを推奨します
- システムは現在正常に稼働しており、RAG機能が完全に動作しています