#!/usr/bin/env bash
# 啟動 VANTA Godot 客戶端
# 用法: bash scripts/run_client.sh [scene]   (scene = main | showcase，預設 main)
set -e
cd "$(dirname "$0")/.."

# 檢查 Godot 二進位
GODOT="${GODOT:-godot}"
if ! command -v "$GODOT" >/dev/null 2>&1; then
  echo "❌ 找不到 Godot 4.4。請先安裝："
  echo "   Windows: https://godotengine.org/download/windows/"
  echo "   macOS:   https://godotengine.org/download/macos/"
  echo "   Linux:   https://godotengine.org/download/linux/"
  echo "   或用環境變數指定: GODOT=/路徑/godot bash scripts/run_client.sh"
  exit 1
fi

# 確保素材已匯出
if [ ! -f client/assets/asset_index.json ]; then
  echo "=== 素材尚未匯出，先執行工具鏈 + 匯出 ==="
  python3 -m tools.cli all
  python3 -m tools.godot.export
fi

SCENE="$1"
if [ "$SCENE" = "showcase" ]; then
  echo "=== 開啟動畫展示場 (showcase.tscn) ==="
  "$GODOT" -e --path client showcase.tscn
else
  echo "=== 開啟對戰客戶端 (main.tscn) ==="
  "$GODOT" -e --path client
fi
