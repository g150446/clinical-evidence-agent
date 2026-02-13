# Cloud Run + ngrok連携ステータス

## 実装完了のサマリ

### 作成したファイル

| ファイル | 目的 | 状態 |
|---------|------|--------|
| `Dockerfile.frontend` | Frontend用Dockerfile（未使用） | ✅ 作成済み |
| `frontend/Dockerfile` | Frontend用Dockerfile | ✅ 作成済み |
| `templates/config.js` | 環境変数設定 | ✅ 作成済み |
| `templates/index.html` | API URL対応 | ✅ 修正済み |
| `.gcloudignore` | Frontendデプロイ用調整 | ✅ 修正済み |

### デプロイ完了

**Cloud Run Frontend:**
- ✅ デプロイ完了
- ✅ URL: https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
- ✅ アクセス可能

**Flask Backend:**
- ✅ 実行中（PID: 76571）
- ✅ ポート8080でリスニング
- ✅ Ollama: OK, Qdrant: OK

---

## 現在の状態

### Cloud Run環境変数

```
API_BASE_URL = http://localhost:8080
```

**注意:** これはテンポラリ設定です。ハッカソンで参加者と共有する前にngrok URLに更新する必要があります。

### ngrokの問題点

**エラーメッセージ:**
```
ERROR: authentication failed: Your account is limited to 1 simultaneous ngrok agent sessions.
```

**原因:**
- ngrokの無料アカウントは同時セッション数に制限あり
- 以前のセッションがダッシュボードで残っている可能性
- 同時に複数のエンドポイントを開けない制限

---

## 対策

### 対策1: ngrokダッシュボードでセッション管理

1. **ダッシュボードにアクセス:**
   - URL: https://dashboard.ngrok.com/agents

2. **既存のセッションを停止:**
   - 実行中のトンネルがあればすべて停止
   - ブラウザで複数のngrokタブを閉じる

3. **ngrok再起動:**
   ```bash
   # まず既存のプロセスを停止
   pkill -f ngrok
   
   # 再起動
   ngrok http 8080
   ```

### 対策2: Cloud Run環境変数をngrok URLに更新

ngrokが正常に起動したら、以下のコマンドでCloud Runの環境変数を更新：

```bash
# ngrok URLを取得（例）
NGROK_URL="https://abc123-def45.ngrok-free.app"

# Cloud Runに更新
gcloud run services update clinical-evidence-frontend \
  --region asia-northeast1 \
  --set-env-vars="API_BASE_URL=${NGROK_URL}"
```

### 対策3: 代替案（ngrokが動かない場合）

#### 代替A: ローカルネットワークでの共有

ハッカソン会場が同じローカルネットワークの場合：
- 参加者にローカルIPアドレスを共有
- Cloud Runではなくローカルサーバーを使用

#### 代替B: 他のトンネリングサービス

- **localtunnel:** 無料、セッション制限なし
- **Cloudflare Tunnel:** 無料、安定性が高い
- **pagekite:** 無料、設定が簡単

#### 代替C: Tailscale Funnel

- ハッカソン期間延長の場合、Tailscale Funnelの検討
- 固定URL、セキュリティ向上

---

## テスト方法

### テスト1: Cloud Run Frontendへのアクセス

1. ブラウザで以下のURLを開く:
   ```
   https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
   ```

2. 右上のステータスバーを確認:
   - ✅ Ollama: OK
   - ✅ Qdrant: OK

3. クエリを入力して実行:
   - モード: Direct / RAG / Compare
   - テストクエリ例:
     - "What is semaglutide?"
     - "glp-1受容体作動薬は週1回でも体重減少作用がありますか？"

### テスト2: RAG機能の確認

1. 「RAG」モードを選択
2. 医療クエリを入力
3. 「実行」をクリック
4. 確認すべき点:
   - ✅ 検索コンテキストが表示される（論文リスト）
   - ✅ MedGemmaが回答を生成
   - ✅ エラーなし

---

## 次のステップ

### 手順1: ngrokダッシュボードでセッションをクリア

1. https://dashboard.ngrok.com/agents にアクセス
2. すべてのアクティブなセッションを停止

### 手順2: ngrokを起動

```bash
# 既存のプロセスを停止
pkill -f ngrok

# 新規に起動
ngrok http 8080
```

### 手順3: ngrok URLを確認

ターミナルに表示されるURLをコピー:
```
https://xxxxx.ngrok-free.app
```

### 手順4: Cloud Run環境変数を更新

```bash
export NGROK_URL="https://xxxxx.ngrok-free.app"
gcloud run services update clinical-evidence-frontend \
  --region asia-northeast1 \
  --set-env-vars="API_BASE_URL=${NGROK_URL}"
```

### 手順5: 最終テスト

1. Cloud Run URLを再読み込み（Cmd+Shift+R）
2. クエリを実行
3. API通信が正常に行われているか確認

---

## ファイル構成

```
/Users/g150446/projects/clinical-evidence-agent/
├── frontend/                  # Frontendデプロイ用サブディレクトリ
│   ├── Dockerfile           # Nginx + index.html
│   └── index.html          # テンプレートのコピー
├── templates/
│   ├── index.html          # API URL対応済み
│   └── config.js           # 環境変数設定
├── app.py                  # Flask Backend（ローカル実行）
├── scripts/                # Pythonスクリプト群
├── .gcloudignore           # Frontendデプロイ設定
└── stop_flask.sh          # Flask停止スクリプト
```

---

## トラブルシューティング

### 問題1: Cloud Run Frontendにアクセスできない

**対処:**
```bash
# サービスのステータス確認
gcloud run services describe clinical-evidence-frontend \
  --region asia-northeast1 \
  --format='value(status.url, status.latestReadyRevisionName)'

# 最新のデプロイメントを確認
gcloud run revisions list clinical-evidence-frontend \
  --region asia-northeast1
```

### 問題2: APIエラーが表示される

**対処:**
1. ブラウザのコンソールを開く（F12またはCmd+Option+I）
2. エラーメッセージを確認
3. API_BASE_URL環境変数を確認:
   ```bash
   gcloud run services describe clinical-evidence-frontend \
     --region asia-northeast1 \
     --format='flattened(env)[].name, flattened(env)[].value'
   ```

### 問題3: RAG機能が動作しない

**対処:**
1. Flaskプロセスが実行中か確認:
   ```bash
   ps aux | grep "app.py" | grep -v grep
   ```

2. Qdrantデータベースが存在するか確認:
   ```bash
   ls -la qdrant_medical_db/
   ```

3. Flaskログを確認:
   ```bash
   tail -50 /tmp/flask.log
   ```

---

## まとめ

| 項目 | 状態 |
|------|--------|
| Frontendデプロイ | ✅ 完了（Cloud Run） |
| Backend起動 | ✅ 完了（ローカルFlask） |
| API通信 | ⚠️  テンポラリ設定（localhost） |
| ngrok起動 | ❌ セッション制限により未完了 |
| 統合テスト | ⚠️  ngrok URL設定後に実施必要 |

---

**次に行うべきこと:**
1. ngrokダッシュボードでセッションをクリア
2. ngrokを再起動
3. Cloud Run環境変数をngrok URLに更新
4. 最終統合テストを実施