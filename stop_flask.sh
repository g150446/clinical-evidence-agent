#!/bin/bash

# stop_flask.sh - Flaskサーバーを停止するスクリプト

echo "Flaskプロセスを検索中..."

# Flaskプロセスを検索して停止
PIDS=$(ps aux | grep "app.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "実行中のFlaskプロセスは見つかりませんでした。"
else
    echo "以下のFlaskプロセスを停止します:"
    echo "$PIDS"
    echo "$PIDS" | xargs kill
    
    # 2秒待機
    sleep 2
    
    # 確認
    REMAINING=$(ps aux | grep "app.py" | grep -v grep | wc -l)
    if [ "$REMAINING" -eq 0 ]; then
        echo "すべてのFlaskプロセスを停止しました。"
    else
        echo "警告: すべてのプロセスを停止できませんでした。強制終了を試行します。"
        echo "$PIDS" | xargs kill -9
        sleep 1
        echo "強制終了完了。"
    fi
    
    # ポート8080の使用状況を確認
    if lsof -i :8080 >/dev/null 2>&1; then
        echo "警告: ポート8080はまだ使用中です。"
    else
        echo "ポート8080は解放されました。"
    fi
fi