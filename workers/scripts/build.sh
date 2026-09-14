#!/usr/bin/env bash
# 複製模擬核心（server/）進打包目錄，然後部署。
# 用法: bash scripts/build.sh [deploy|dev]
set -e
cd "$(dirname "$0")/.."

echo "=== 複製 server/ → src/server/ ==="
rm -rf src/server
cp -r ../server src/server
find src/server -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# 產出檔案清單供檢查
echo "server/ 檔案數: $(find src/server -name '*.py' | wc -l)"

if [ "$1" = "deploy" ]; then
  uvx --from workers-py pywrangler deploy
elif [ "$1" = "dev" ]; then
  uvx --from workers-py pywrangler dev
else
  echo "完成 ✔ 執行 'uvx --from workers-py pywrangler dev' 本機開發，或 'pywrangler deploy' 部署。"
fi
