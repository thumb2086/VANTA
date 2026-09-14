#!/usr/bin/env bash
# M3 PyO3 橋接：建置 Rust 擴展 → 部署到 server/core/_rust → 跑雙軌測試 + 基準
# 用法: bash scripts/run_rust_swap.sh
set -e
cd "$(dirname "$0")/.."

export RUSTUP_HOME=/var/tmp/.rustup CARGO_HOME=/var/tmp/.cargo PATH="/var/tmp/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
  echo "❌ 找不到 cargo。安裝: curl https://sh.rustup.rs -sSf | sh"
  exit 1
fi

echo "=== 1) 建置 vanta_core_rs（PyO3 擴展）==="
cd rust/vanta_core_rs
cargo build --release
mkdir -p ../../server/core/_rust
cp target/release/libvanta_core_rs.so ../../server/core/_rust/
cd ../..

echo ""
echo "=== 2) M3 雙軌測試（Rust 核心 vs Python 核心位元組一致）==="
python3 -m pytest tests/test_rust_core.py tests/test_rust_batch.py tests/test_rust_worldsim.py -v

echo ""
echo "=== 3) 基準（批次模式 = 正確用法）==="
python3 -m pytest tests/test_rust_batch.py::test_batch_faster_than_python -s -q 2>&1 | grep bench

echo ""
echo "完成 ✔ Rust 擴展已部署：server/core/_rust/libvanta_core_rs.so"
echo "  伺服器預設用 Python 核心（細粒度單步無淨增益，見 docs/07 M3）；"
echo "  VANTA_USE_RS=1 可強制 Rust 單步（雙軌驗證用）；批次 API 供 M4 世界迴圈 Rust 化。"
