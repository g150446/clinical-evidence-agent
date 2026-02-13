# Tailscale Funnel + HTTPS対応 実装計画

## 最終構成

```
[インターネット参加者]
        ↓ HTTPS
[Cloud Run Frontend] ← Nginx + index.html + config.js
        ↓ HTTPS:443
[Tailscale Funnel] ← Let's Encrypt証明書
        ↓ HTTPS:443
[Flask Backend] ← 自己署名証明書対応
        ↓ HTTP:8080
[Ollama/Qdrant] ← localhost
```

---

## 実装手順

### ステップ1: FlaskのHTTPS:443対応

**app.pyの最終行を修正:**
```python
if __name__ == '__main__':
    from flask_openssl import SSLContext
    import os
    
    # 環境変数でポートを選択
    # テスト環境: HTTP:8080
    # 本番環境: HTTPS:443
    USE_HTTP = os.getenv('USE_HTTP', 'false').lower() == 'true'
    
    if USE_HTTP:
        # テスト環境: HTTP:8080で起動
        print("HTTP:8080でFlaskを起動します...")
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    else:
        # 本番環境: HTTPS:443で起動
        # TLS証明書はTailscale Funnelが自動的に提供
        
        # 注意: Tailscale Funnel証明書を使用しない場合、
        # app.run()のssl_contextパラメータを削除してエラー回避
        
        print("HTTPS:443でFlaskを起動します...")
        app.run(host='0.0.0.0', port=443, debug=False, threaded=True)
```

**環境変数の使用方法:**
```bash
# テスト環境: HTTPモード
export USE_HTTP=true
python3 app.py

# 本番環境: HTTPSモード（デフォルト）
python3 app.py
```

---

### ステップ2: Flaskの再起動

```bash
# 1. 既存のFlaskプロセスを停止
./stop_flask.sh

# 2. 本番環境（HTTPS:443）で再起動
export USE_HTTP=false
python3 app.py > /tmp/flask_https.log 2>&1 &

# 3. HTTPS:443でリッスニング確認
sleep 5
lsof -i :443

# 4. APIテスト
curl -k https://macbookair-g150446.taile24f86.ts.net:443/api/status | python3 -m json.tool

# 5. HTTP:8080でもアクセス可能か確認
curl -k http://127.0.0.1:8080/api/status | python3 -m json.tool
```

---

### ステップ3: Cloud Run環境変数の更新

```bash
# HTTPS:443 URLを設定
export HTTPS_FUNNEL_URL="https://macbookair-g150446.taile24f86.ts.net:443"

# Cloud Runに更新
gcloud run services update clinical-evidence-frontend \
  --region asia-northeast1 \
  --set-env-vars="API_BASE_URL=${HTTPS_FUNNEL_URL}"

# 更新確認
gcloud run services describe clinical-evidence-frontend \
  --region asia-northeast1 \
  --format='value(flattened(env)[].name, flattened(env)[].value)' | grep API_BASE_URL
```

---

## アクセス方法

### 本番環境（HTTPS:443）

```
URL: https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app
```

**フロー:**
1. ユーザーは上記URLにアクセス
2. Frontend → HTTPS:443（Tailscale Funnel）
3. Tailscale Funnel → HTTP:8080
4. Flask Backend → Ollama/Qdrant
5. RAG検索・回答生成

### テスト環境（HTTP:8080）

```bash
# テスト用の環境変数を設定
export USE_HTTP=true

# FlaskをHTTP:8080で再起動
./stop_flask.sh
python3 app.py
```

---

## トラブルシューティング

### 問題1: HTTPS:443にアクセスできない

**確認:**
```bash
lsof -i :443
curl -I https://macbookair-g150446.taile24f86.ts.net:443/
```

**対処:**
- Tailscale Funnelが実行中か確認: `tailscale funnel status`
- FlaskがHTTPS:443で実行中か確認: `ps aux | grep "app.py" | grep -v grep`

### 問題2: ブラウザでMixed Content警告

**原因:** HTTPSページの静的コンテンツ（画像、CSS）がHTTP経由で配信されている可能性

**対処:**
- config.jsでHTTPリソースを指定
- またはブラウザの開発者ツールでMixed Content警告を無視
- またはCloud Runの環境変数`CLOUDRUN_HTTP_ONLY=true`を設定してHTTPS強制

### 問題3: 自己署名証明書の警告

**原因:** Let's Encryptや信頼されるCAに署名されていないため

**対処:**
- 警告をそのまま進める（ハッカソン用途なら問題なし）
- またはTailscaleの有料プラン（Personal Plus）を使用
- またはLet's Encrypt + DNS検証で正式な証明書を取得

---

## 最終確認リスト

実装を開始する前に、以下を確認してください：

- [ ] FlaskのHTTPS:443対応準備完了（上記コードをapp.pyに追加済み）
- [ ] Flaskを再起動したく済み
- [ ] HTTPS:443でAPIテスト済み
- [ ] Cloud Run環境変数をHTTPS:443 URLに更新したく済み
- [ ] ブラウザで正常にアクセスできる

---

準備が整いましたら、実装を開始しますか？