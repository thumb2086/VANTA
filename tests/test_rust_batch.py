"""M3 PyO3 批次 API：正確性（位元組一致）+ 效能（批次攤平邊界成本）。"""

import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.core import rs_bridge  # noqa: E402

pytestmark = pytest.mark.skipif(not rs_bridge.rs_available(),
                                reason="Rust 擴展未建置（先跑 scripts/run_rust_swap.sh）")

DT = 1.0 / 128.0


def _golden_inputs():
    from rust.parity.golden import make_inputs

    return make_inputs()


def test_batch_matches_python_byte_exact():
    """批次 Rust 移動 vs 逐玩家 Python 移動 → 位元組級一致（10 玩家 × 2000 ticks）。"""
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()
    N = 10
    pys = [MovementController(MovementConfig(), 0.0) for _ in range(N)]
    batch = rs_bridge.RustMovementBatch(MovementConfig(), 0.0, count=N)

    for inp in inputs:
        # Python 逐玩家
        for p in pys:
            p.step(inp, DT)
        # Rust 批次
        batch.step_all([inp.forward] * N, [inp.strafe] * N, [inp.walk] * N,
                       [inp.crouch] * N, [inp.jump] * N, [1.0] * N, DT)
        # 逐 tick 比對
        rs_pos = batch.positions()
        for i in range(N):
            assert rs_pos[i] == (pys[i].pos.x, pys[i].pos.y, pys[i].pos.z), \
                f"tick 分歧（玩家 {i}）"


def test_batch_speed_mult_matches():
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()[:500]
    py = MovementController(MovementConfig(), 0.0)
    batch = rs_bridge.RustMovementBatch(MovementConfig(), 0.0, count=1)
    mults = [1.25]  # 單玩家
    for inp in inputs:
        py.step(inp, DT, 1.25)
        batch.step_all([inp.forward], [inp.strafe], [inp.walk], [inp.crouch],
                       [inp.jump], mults, DT)
        p = batch.positions()[0]
        assert p == (py.pos.x, py.pos.y, py.pos.z)


def test_batch_set_state_roundtrip():
    """批次支援狀態回寫（重生/碰撞回彈用途）。"""
    batch = rs_bridge.RustMovementBatch(count=2)
    batch.set_state(1, 10.0, 1.0, 2.0, 0.0, 0.0, 5.0)
    pos = batch.positions()
    vel = batch.velocities()
    assert pos[1] == (10.0, 1.0, 2.0)
    assert vel[1] == (0.0, 0.0, 5.0)


def test_batch_faster_than_python():
    """批次模式效能：10 玩家 × 2000 ticks，Rust 批次應明顯快於 Python 逐玩家。"""
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()
    N = 10
    reps = 5

    # 熱身
    batch = rs_bridge.RustMovementBatch(MovementConfig(), 0.0, count=N)
    for inp in inputs:
        batch.step_all([inp.forward] * N, [inp.strafe] * N, [inp.walk] * N,
                       [inp.crouch] * N, [inp.jump] * N, [1.0] * N, DT)

    fwd = [i.forward for i in inputs]
    str_ = [i.strafe for i in inputs]
    wk = [i.walk for i in inputs]
    cr = [i.crouch for i in inputs]
    jp = [i.jump for i in inputs]

    t0 = time.perf_counter()
    for _ in range(reps):
        b = rs_bridge.RustMovementBatch(MovementConfig(), 0.0, count=N)
        for k in range(len(inputs)):
            b.step_all([fwd[k]] * N, [str_[k]] * N, [wk[k]] * N, [cr[k]] * N,
                       [jp[k]] * N, [1.0] * N, DT)
    rs_t = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(reps):
        pys = [MovementController(MovementConfig(), 0.0) for _ in range(N)]
        for inp in inputs:
            for p in pys:
                p.step(inp, DT)
    py_t = time.perf_counter() - t0

    assert rs_t < py_t, f"批次未更快: rs={rs_t:.3f}s py={py_t:.3f}s"
    print(f"\n[bench] 10玩家×{len(inputs)}ticks×{reps}遍: "
          f"Rust批次 {rs_t:.3f}s vs Python {py_t:.3f}s → {py_t / max(rs_t, 1e-9):.1f}x")
