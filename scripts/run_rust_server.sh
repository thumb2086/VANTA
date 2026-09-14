#!/usr/bin/env bash
# M5 純 Rust 伺服器：建置 + 基準 + E2E（Python GameClient 連線）
# 用法: bash scripts/run_rust_server.sh
set -e
cd "$(dirname "$0")/.."

export RUSTUP_HOME=/var/tmp/.rustup CARGO_HOME=/var/tmp/.cargo PATH="/var/tmp/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
  echo "❌ 找不到 cargo（/var/tmp 的 toolchain 可能被 session 清除）"
  echo "   執行: bash scripts/setup_rust.sh"
  exit 1
fi

echo "=== 1) 建置 vanta_server ==="
cd rust/vanta_server
cargo build --release
cd ../..

echo ""
echo "=== 2) 基準（128Hz 10 玩家全力模擬）==="
./rust/vanta_server/target/release/vanta_server --port 0 --bench-ticks 76800

echo ""
echo "=== 3) E2E 測試（Rust 伺服器 ↔ Python GameClient）==="
python3 -m pytest tests/test_rust_server_e2e.py -v

echo ""
echo "完成 ✔ 純 Rust 權威伺服器（M5 骨架）可用："
echo "  ./rust/vanta_server/target/release/vanta_server --port 7777"
