#!/bin/bash
# Flask Server Management Script
# Usage:
#   ./run_flask.sh [start|stop|restart|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASK_PID_FILE="$SCRIPT_DIR/.flask_pid"
FLASK_LOG="$SCRIPT_DIR/flask.log"

start_flask() {
    echo "=== Starting Flask Server ==="

    # Check if already running
    if [ -f "$FLASK_PID_FILE" ]; then
        existing_pid=$(cat "$FLASK_PID_FILE")
        if ps -p "$existing_pid" > /dev/null 2>&1; then
            echo "✗ Flask is already running (PID: ${existing_pid})"
            echo "Use ./run_flask.sh status to check status"
            return 1
        else
            rm -f "$FLASK_PID_FILE"
        fi
    fi

    cd "$SCRIPT_DIR"

    nohup python3 app.py > "$FLASK_LOG" 2>&1 &
    flask_pid=$!
    echo "$flask_pid" > "$FLASK_PID_FILE"

    sleep 2
    if ps -p "$flask_pid" > /dev/null 2>&1; then
        echo "✓ Flask started successfully (PID: ${flask_pid})"
        echo "  - Port: 8080"
        echo "  - Log: ${FLASK_LOG}"
        echo ""
        echo "=== Flask Server Status ==="
        echo "To stop: ./run_flask.sh stop"
        echo "To check status: ./run_flask.sh status"
    else
        echo "✗ Flask failed to start"
        rm -f "$FLASK_PID_FILE"
        return 1
    fi
}

stop_flask() {
    echo "=== Stopping Flask Server ==="

    if [ ! -f "$FLASK_PID_FILE" ]; then
        echo "✗ No Flask PID file found"
        return 1
    fi

    pid=$(cat "$FLASK_PID_FILE")

    if [ -z "$pid" ]; then
        echo "✗ PID file is empty"
        return 1
    fi

    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "  Sending SIGTERM to ${pid}..."
        kill -TERM "$pid" 2>/dev/null

        timeout=5
        while [ $timeout -gt 0 ]; do
            if ! ps -p "$pid" > /dev/null 2>&1; then
                echo "  ✓ Process ${pid} stopped gracefully"
                rm -f "$FLASK_PID_FILE"
                echo ""
                echo "=== Flask Server Status ==="
                echo "✓ Flask server stopped"
                return 0
            fi
            sleep 1
            timeout=$((timeout - 1))
        done

        if ps -p "$pid" > /dev/null 2>&1; then
            echo "  Force killing ${pid}..."
            kill -KILL "$pid" 2>/dev/null
            sleep 1
            rm -f "$FLASK_PID_FILE"
            return 0
        fi
    fi

    echo "✗ Failed to stop Flask server"
    return 1
}

restart_flask() {
    echo "=== Restarting Flask Server ==="

    if [ -f "$FLASK_PID_FILE" ]; then
        pid=$(cat "$FLASK_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            stop_flask
        fi
    fi

    sleep 1
    start_flask
}

show_status() {
    echo "=== Flask Server Status ==="
    echo ""

    if [ ! -f "$FLASK_PID_FILE" ]; then
        echo "✗ Flask PID file not found"
        return 1
    fi

    pid=$(cat "$FLASK_PID_FILE")

    if [ -z "$pid" ]; then
        echo "✗ PID file is empty"
        return 1
    fi

    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "✗ Process ${pid} is not running"
        rm -f "$FLASK_PID_FILE"
        return 1
    fi

    echo "✓ Flask server is running"
    echo "  PID: ${pid}"
    echo "  Port: 8080"
    echo "  Log: ${FLASK_LOG}"
    echo ""
    echo "Recent log entries:"
    if [ -f "$FLASK_LOG" ]; then
        tail -10 "${FLASK_LOG}" 2>/dev/null || echo "  (No log file)"
    else
        echo "  (No log file)"
    fi
    echo ""
    echo "Actions:"
    echo "  Stop: ./run_flask.sh stop"
    echo "  Restart: ./run_flask.sh restart"
    echo "  Status: ./run_flask.sh status"
}

case "${1:-}" in
    start)
        start_flask
        ;;
    stop)
        stop_flask
        ;;
    restart)
        restart_flask
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: ./run_flask.sh [start|stop|restart|status]"
        echo ""
        echo "Commands:"
        echo "  start   - Start Flask server in background"
        echo "  stop    - Stop Flask server gracefully"
        echo "  restart - Restart Flask server"
        echo "  status  - Show Flask server status"
        exit 1
        ;;
esac
