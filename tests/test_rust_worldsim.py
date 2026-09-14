"""M4 世界迴圈 Rust 化（WorldSim）：雙軌位元組一致 + 效能實測。"""

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


@pytest.fixture(autouse=True)
def _clean_env():
    """每個測試後還原 VANTA_USE_RS，避免影響其他測試檔。"""
    yield
    os.environ.pop("VANTA_USE_RS", None)


def _run_world(use_rs: bool, ticks: int = 400):
    os.environ["VANTA_USE_RS"] = "1" if use_rs else "0"
    from server.core.movement import MoveInput
    from server.game.entities import World
    from server.game.match import RoundPhase

    w = World(seed=7)
    w.start_match()
    w.match.phase = RoundPhase.ACTION
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    inp[1] = MoveInput(strafe=1.0)
    inp[2] = MoveInput(forward=1.0, strafe=1.0)
    inp[3] = MoveInput(jump=True)
    inp[4] = MoveInput(forward=1.0, walk=True)
    inp[5] = MoveInput(forward=1.0, crouch=True)
    for _ in range(ticks):
        w.step(inp, DT)
    return [(p.pos.x, p.pos.y, p.pos.z, p.vel.x, p.vel.y, p.vel.z,
             p.on_ground, p.crouching, p.walking) for p in w.players]


def test_worldsim_matches_python_byte_exact():
    """Rust 世界迴圈 vs Python 世界迴圈：10 玩家 × 400 ticks 完全一致（含碰撞）。"""
    py = _run_world(False)
    rs = _run_world(True)
    assert rs == py, "Rust 世界迴圈與 Python 分歧"


def test_worldsim_collision_active():
    """Rust 世界迴圈碰撞生效：玩家跑向牆前應停止（不穿牆）。"""
    os.environ["VANTA_USE_RS"] = "1"
    from server.core.movement import MoveInput
    from server.game.entities import World
    from server.game.match import RoundPhase

    w = World(seed=7)
    w.start_match()
    w.match.phase = RoundPhase.ACTION
    # 放一道牆在 z=3（p0 從 -12 起跑，400 ticks 必撞上）
    from server.core.math_core import Vec3
    from server.game.mapdata import Wall

    w.map_data.walls.append(Wall(Vec3(-10, 0, 3), Vec3(10, 4, 3.2), "concrete"))
    w._rs_world = None  # 牆變了 → 重建 Rust 世界（含新牆）
    from server.core import rs_bridge as _rb

    walls = [(x.mn.x, x.mn.y, x.mn.z, x.mx.x, x.mx.y, x.mx.z) for x in w.map_data.walls]
    w._rs_world = _rb.RustWorldSim(walls, None, 0.0, count=10)
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    for _ in range(500):
        w.step(inp, DT)
    p = w.players[0]
    assert p.pos.z <= 3.0 - 0.35 + 0.05, f"穿牆: z={p.pos.z}"
    assert abs(p.vel.z) < 0.01, f"撞牆速度未消除: {p.vel}"


def test_worldsim_respawn_respected():
    """重生/外部改位置 → 被 Rust 尊重（sync_states 生效）。"""
    os.environ["VANTA_USE_RS"] = "1"
    from server.core.movement import MoveInput
    from server.game.entities import World
    from server.game.match import RoundPhase

    w = World(seed=7)
    w.start_match()
    w.match.phase = RoundPhase.ACTION
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    for _ in range(50):
        w.step(inp, DT)
    # 直接改位置（模擬重生）
    from server.core.math_core import Vec3

    w.players[0].pos = Vec3(0, 0, -13)
    w.players[0].vel = Vec3()
    for _ in range(20):
        w.step(inp, DT)
    # 應從新位置繼續跑（Rust 尊重外部修改）
    assert w.players[0].pos.z > -12.5


def test_worldsim_faster_than_python():
    """世界迴圈效能：Rust（每 tick 2 次跨邊界）vs Python，應明顯更快。"""
    reps = 20
    ticks = 400

    def bench(use_rs):
        os.environ["VANTA_USE_RS"] = "1" if use_rs else "0"
        t0 = time.perf_counter()
        for _ in range(reps):
            _run_world(use_rs, ticks)
        return time.perf_counter() - t0

    py_t = bench(False)
    rs_t = bench(True)
    assert rs_t < py_t, f"Rust 未更快: rs={rs_t:.3f}s py={py_t:.3f}s"
    print(f"\n[bench] 10玩家×{ticks}ticks×{reps}遍: Rust {rs_t:.3f}s vs Python {py_t:.3f}s "
          f"→ {py_t / max(rs_t, 1e-9):.1f}x")
