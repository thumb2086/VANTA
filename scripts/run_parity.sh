#!/usr/bin/env bash
# Rust 遷移 parity 驗證：Python 黃金資料 ↔ Rust 核心位元組級比對 + 基準
# 用法: bash scripts/run_parity.sh
set -e
cd "$(dirname "$0")/.."

export RUSTUP_HOME=/var/tmp/.rustup CARGO_HOME=/var/tmp/.cargo PATH="/var/tmp/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
  echo "❌ 找不到 cargo。安裝: curl https://sh.rustup.rs -sSf | sh"
  exit 1
fi

echo "=== 1) 產生 Python 黃金資料 ==="
python3 rust/parity/golden.py

echo ""
echo "=== 2) Rust 核心 parity 比對（M1 移動 + M2 後座力/彈道/封包）==="
cd rust/parity
cargo build --release
./target/release/vanta_parity
./target/release/parity_recoil
./target/release/parity_ballistics
./target/release/parity_protocol

echo ""
echo "=== 3) 效能基準（Rust vs Python）==="
cargo build --release --bin bench
./target/release/bench inputs.bin
cd ../..
python3 - <<'EOF'
import sys, struct, time
sys.path.insert(0, '.')
from server.core.movement import MovementController, MoveInput
data = open('rust/parity/inputs.bin','rb').read()
n = len(data)//17
inputs = []
for i in range(n):
    off = i*17
    fwd, str_ = struct.unpack('<dd', data[off:off+16])
    fl = data[off+16]
    inputs.append(MoveInput(forward=fwd, strafe=str_, walk=bool(fl&1), crouch=bool(fl&2), jump=bool(fl&4)))
c = MovementController()
for inp in inputs: c.step(inp, 1/128)
players, reps = 10, 3
t0 = time.perf_counter()
for _ in range(reps):
    ctrls = [MovementController() for _ in range(players)]
    for inp in inputs:
        for ctrl in ctrls:
            ctrl.step(inp, 1/128)
el = time.perf_counter()-t0
total = reps*n*players
print(f"Python: {total} ticks 耗時 {el:.3f}s → {total/el/1e6:.1f} M ticks/s | 每 tick {el/total*1e9:.0f} ns")
EOF
