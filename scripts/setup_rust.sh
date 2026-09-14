#!/usr/bin/env bash
# 安裝/重建 Rust 工具鏈與 vanta_core_rs 擴展（工作區保持輕量：toolchain 放 /tmp）
# 用法: bash scripts/setup_rust.sh
set -e

# toolchain 放 /var/tmp（不佔工作區快照配額；session 間可能被清，需要時重跑本腳本）
export RUSTUP_HOME=/var/tmp/.rustup CARGO_HOME=/var/tmp/.cargo PATH=/var/tmp/.cargo/bin:$PATH

if ! command -v cargo >/dev/null 2>&1; then
  echo "=== 安裝 Rust toolchain（~15s）==="
  curl -sSf https://sh.rustup.rs -o /var/tmp/rustup.sh
  sh /var/tmp/rustup.sh -y --profile minimal --default-toolchain stable >/dev/null 2>&1
  export PATH=/var/tmp/.cargo/bin:$PATH
fi
echo "cargo: $(cargo --version)"

echo "=== 建置 vanta_core_rs ==="
cd "$(dirname "$0")/../rust/vanta_core_rs"
cargo build --release
mkdir -p ../../server/core/_rust
cp target/release/libvanta_core_rs.so ../../server/core/_rust/
echo "完成 ✔ 擴展已部署: server/core/_rust/libvanta_core_rs.so"
python3 -c "import sys; sys.path.insert(0,'.'); from server.core import rs_bridge; print('rs_available:', rs_bridge.rs_available())" 2>/dev/null || true
