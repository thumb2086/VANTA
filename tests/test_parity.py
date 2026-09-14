"""Rust 遷移 parity：黃金資料 + 跨語言位元組級比對（Rust 存在才執行）。"""

import os
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "rust", "parity")
DT = 1.0 / 128.0


@pytest.fixture(scope="module")
def golden():
    """重新產生黃金資料並回傳檔案路徑。"""
    sys.path.insert(0, ROOT)
    from rust.parity import golden as g  # noqa: N814
    from rust.parity.golden import make_inputs, main as gen_main

    gen_main()
    inputs = os.path.join(PARITY, "inputs.bin")
    states = os.path.join(PARITY, "states.bin")
    assert os.path.isfile(inputs) and os.path.isfile(states)
    return inputs, states


def _cargo():
    cargo = shutil.which("cargo")
    if cargo is None:
        home = os.path.expanduser("/var/tmp/.cargo/bin/cargo")
        if os.path.isfile(home):
            cargo = home
    return cargo


def _rust_env():
    """Linux 開發機把工具鏈放在 /var/tmp；其他平台沿用目前環境（跨平台）。"""
    if os.path.isdir("/var/tmp/.cargo/bin"):
        return dict(os.environ, RUSTUP_HOME="/var/tmp/.rustup", CARGO_HOME="/var/tmp/.cargo",
                    PATH="/var/tmp/.cargo/bin" + os.pathsep + os.environ.get("PATH", ""))
    return dict(os.environ)


def test_golden_structure(golden):
    """黃金資料格式正確：每 tick 17B 輸入、48B 狀態、與 Python 模擬一致。"""
    inputs, states = golden
    with open(inputs, "rb") as f:
        raw_in = f.read()
    n = len(raw_in) // 17
    assert n * 17 == len(raw_in)
    assert n == 2000

    # 以 Python 重跑並與 states.bin 比對（自我一致性）
    from server.core.movement import MovementConfig, MovementController, MoveInput

    ctrl = MovementController(MovementConfig())
    with open(states, "rb") as f:
        raw_st = f.read()
    for i in range(n):
        off = i * 17
        fwd, str_ = struct.unpack("<dd", raw_in[off : off + 16])
        flags = raw_in[off + 16]
        ctrl.step(MoveInput(forward=fwd, strafe=str_, walk=bool(flags & 1),
                            crouch=bool(flags & 2), jump=bool(flags & 4),
                            ads=bool(flags & 8)), DT)
        expect = struct.unpack("<dddddd", raw_st[i * 48 : i * 48 + 48])
        got = (ctrl.pos.x, ctrl.pos.y, ctrl.pos.z, ctrl.vel.x, ctrl.vel.y, ctrl.vel.z)
        assert got == expect, f"tick {i}: 黃金資料與 Python 模擬不一致"


@pytest.mark.skipif(_cargo() is None, reason="cargo 未安裝（跳過 Rust parity）")
def test_rust_parity(golden):
    """Rust 核心與 Python 黃金資料位元組級一致（遷移藍圖的核心驗收）。"""
    inputs, states = golden
    env = _rust_env()
    # 建置
    subprocess.run([_cargo(), "build", "--release"], cwd=PARITY, check=True,
                   env=env, capture_output=True)
    out = os.path.join(PARITY, "states_rust.bin")
    r = subprocess.run([os.path.join(PARITY, "target", "release", "vanta_parity"),
                        inputs, states, out], cwd=PARITY, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PARITY OK" in r.stdout, r.stdout
    with open(states, "rb") as f:
        expect = f.read()
    with open(out, "rb") as f:
        got = f.read()
    assert got == expect, "Rust 輸出與 Python 黃金資料位元組不一致"


@pytest.mark.skipif(_cargo() is None, reason="cargo 未安裝")
def test_rust_bench_runs(golden):
    """Rust 基準程式可執行且產出合理數字（無迴圈優化假象）。"""
    inputs, _ = golden
    env = _rust_env()
    subprocess.run([_cargo(), "build", "--release", "--bin", "bench"], cwd=PARITY,
                   check=True, env=env, capture_output=True)
    r = subprocess.run([os.path.join(PARITY, "target", "release", "bench"), inputs],
                       cwd=PARITY, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0
    # 每 tick 應在 5~100 ns 之間（防優化假象與防異常慢）
    import re

    m = re.search(r"每 tick ([\d.]+) ns", r.stdout)
    assert m, r.stdout
    ns = float(m.group(1))
    assert 5 <= ns <= 200, f"每 tick {ns}ns 超出合理範圍"
