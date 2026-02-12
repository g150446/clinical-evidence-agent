# Pythonの軽量イメージを使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー
COPY . .

# コンテナ起動時に実行するコマンド (Gunicornを使用)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
