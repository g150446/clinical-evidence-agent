#!/bin/bash

# generate_certs.sh - TLS証明書の生成（自己署名）
# 注意: この証明書はブラウザで警告が表示されます

# �定値
DOMAIN="macbookair-g150446.taile24f86.ts.net"
CERT_DIR="$HOME/.local/share/tailscale/certs"
VALIDITY_DAYS=365

echo "=== TLS証明書の生成開始 ==="
echo "ドメイン: $DOMAIN"
echo "有効期間: $VALIDITY_DAYS 日"

# 証明書ディレクトリの作成
mkdir -p "$CERT_DIR"
echo "証明書ディレクトリ: $CERT_DIR"

# 秘密鍵の生成
echo "プライベートキーを生成中..."
openssl genrsa -out "$CERT_DIR/key.pem" 2048 2>/dev/null

echo "証明書署名要求（CSR）の作成中..."
openssl req -new -key "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.csr" \
  -subj "/C=US/ST=California/L=San Francisco/O=OpenAI/OU=Development/CN=$DOMAIN" \
  -days $VALIDITY_DAYS \
  2>/dev/null

echo "自己署名証明書の作成中..."
openssl x509 -req -days $VALIDITY_DAYS -in "$CERT_DIR/cert.csr" \
  -signkey "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  2>/dev/null

echo "✓ TLS証明書の生成完了！"
echo ""
echo "生成されたファイル:"
ls -la "$CERT_DIR/"
echo ""
echo "注意: この証明書はブラウザで警告が表示されます"
echo "      （自己署名証明書のため）"