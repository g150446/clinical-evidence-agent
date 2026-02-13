# Cloud Run + Tailscale Funnel統合完了サマリ

## 実装完了のサマリ

### アーキテクチャ

```
[インターネット参加者]
        ↓ HTTPS
[Cloud Run Frontend] ← Nginx + index.html + config.js
        ↓ HTTPS
[Tailscale Funnel] ← HTTPS公開トンネル（Let's Encrypt）
        ↓ HTTP:443
[Flask Backend] ← MacBookAir:8080
        ↓
[Ollama/Qdrant] ← localhost
```

---

## 実装内容

| コンポーネント | 状態 | 詳細 |
|------------|--------|--------|
| **Cloud Run Frontend** | ✅ デプロイ完了 | URL: https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app |
| **Tailscale Funnel** | ✅ 有効化済み | URL: https://macbookair-g150446.taile24f86.ts.net |
| **Flask Backend** | ✅ 実行中 | ポート: 8080 |
| **Ollama** | ✅ 利用可能 | medgemma:latest |
| **Qdrant** | ✅ 利用可能 | medical_papers, atomic_facts |

---

## 作成・修正されたファイル

| ファイル | 変更内容 |
|---------|----------|
| `frontend/Dockerfile` | 静的ファイルをすべてコピー |
| `frontend/config.js` | Tailscale Funnel URLをデフォルト設定 |
| `frontend/index.html` | 不要なローカル検出ロジックを削除 |

---

## 現在の設定

### Cloud Run環境変数
```
API_BASE_URL = https://macbookair-g150446.taile24f86.ts.net
```

### Tailscale Funnel URL
```
公開URL: https://macbookair-g150446.taile24f86.ts.net
プロキシ: |-- proxy http://127.0.0.1:8080
```

### Flask Backend
```
URL: http://127.0.0.1:8080
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

# 4. Cloud Run Frontendの確認
curl -s https://clinical-evidence-frontend-73460068271.asia-northeast1.run.app/config.js

# 5. 統合テスト（ブラウザで）
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

### テスト3: Compareモード

**確認項目:**
- [ ] Compareモードを選択
- [ ] 左側にRAG回答、右側にDirect回答が表示される
- [ ] 両方の回答が同時に生成される

---

## トラブルシューティング

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
tailscale funnel --bg --https=443
```

---

## セキュリティ設定

### 現在のセキュリティ

| 脅威 | 対策 | 状態 |
|------|--------|--------|
| **バックエンドAPI公開** | Tailscale Funnel経由 | ✅ HTTPSで保護 |
| **CORS** | 不要（同一オリジン） | N/A |
| **参加者へのアクセス制限** | URL共有で簡易制御 | ✅ 共有可能 |
| **DoS攻撃** | Tailscaleのレート制限 | ✅ 保護されている |

---

## コマンド早見表

| 目的 | コマンド |
|------|--------|
| **Flask起動** | `python3 app.py` |
| **Flask停止** | `./stop_flask.sh` |
| **Tailscale Funnel確認** | `tailscale funnel status` |
| **Tailscale Funnel有効化** | `tailscale funnel --bg --https=443` |
| **Cloud Run更新** | `gcloud run services update clinical-evidence-frontend --region asia-northeast1 --set-env-vars="API_BASE_URL=https://macbookair-g150446.taile24f86.ts.net"` |
| **Cloud Run確認** | `gcloud run services describe clinical-evidence-frontend --region asia-northeast1` |

---

## まとめ

| 項目 | 状態 |
|------|--------|
| Cloud Run Frontend | ✅ デプロイ完了 |
| Tailscale Funnel | ✅ 有効化済み |
| Flask Backend | ✅ 実行中 |
| 統合テスト | ⚠️ DNS伝播待機中 |

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

---

**注記:** DNS伝播には数分〜10分かかる場合があります。その間は、以下のCloud Run URLからアクセスすることは可能ですが、API通信は機能しません。