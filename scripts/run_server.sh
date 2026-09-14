#!/usr/bin/env bash
# 啟動 VANTA 本機權威伺服器（AI 對戰）
# 用法: bash scripts/run_server.sh [port]
set -e
cd "$(dirname "$0")/.."
PORT="${1:-7777}"
echo "=== 啟動 VANTA 權威伺服器 @ 127.0.0.1:${PORT} (AI 對戰) ==="
python3 -u -m tools.godot.serve --ai --port "$PORT"
