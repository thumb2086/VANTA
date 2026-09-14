"""M3 PyO3 橋接：Rust 核心 ↔ Python 核心 雙軌位元組級比對（Rust 擴展存在才執行）。"""

import math
import os
import struct
import sys

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


# --------------------------------------------------------------------- #
# 移動：雙軌位元組級比對（含 speed_mult）
# --------------------------------------------------------------------- #
def test_movement_rust_matches_python_full_script():
    """同一輸入腳本（含反切/跳躍緩衝/隨機）→ Rust 與 Python 每 tick 位置/速度完全一致。"""
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()
    py = MovementController(MovementConfig(), 0.0)
    rs = rs_bridge.RustMovementController(MovementConfig(), 0.0)
    for i, inp in enumerate(inputs):
        py.step(inp, DT)
        rs.step(inp, DT)
        assert rs.pos == py.pos, f"tick {i}: pos 分歧 {rs.pos} vs {py.pos}"
        assert rs.vel == py.vel, f"tick {i}: vel 分歧"
        assert rs.on_ground == py.on_ground
        assert rs.crouching == py.crouching and rs.walking == py.walking
        assert rs.time_since_land == py.time_since_land


def test_movement_rust_matches_python_speed_mult():
    """speed_mult（刺激加速/暈眩）也位元級一致。"""
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()[:800]
    for mult in (1.25, 0.65):
        py = MovementController(MovementConfig(), 0.0)
        rs = rs_bridge.RustMovementController(MovementConfig(), 0.0)
        for i, inp in enumerate(inputs):
            py.step(inp, DT, mult)
            rs.step(inp, DT, mult)
            assert rs.pos == py.pos, f"mult={mult} tick {i}: pos 分歧"


def test_movement_rust_getters_mirror():
    from server.core.movement import MovementConfig, MovementController, MoveInput

    py = MovementController(MovementConfig(), 0.0)
    rs = rs_bridge.RustMovementController(MovementConfig(), 0.0)
    inp = MoveInput(forward=1.0, crouch=True)
    py.step(inp, DT)
    rs.step(inp, DT)
    assert rs.current_max_speed() == py.current_max_speed()
    assert rs.horizontal_speed() == py.horizontal_speed()
    assert rs.speed_ratio() == py.speed_ratio()
    assert rs.crouching is True
    # 定位設定（重生/碰撞回彈）
    rs.pos = __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(1, 2, 3)
    assert rs.pos == __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(1, 2, 3)
    rs.vel = __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 5)
    assert rs.vel.z == 5.0


# --------------------------------------------------------------------- #
# 後座力：Rust 擴展 vs Python 黃金序列
# --------------------------------------------------------------------- #
def test_recoil_rust_matches_python():
    """Rust RecoilController(seed=42) 重放 schedule → 與 Python 序列完全一致。"""
    from server.core.rng import MT19937
    from server.game.recoil import PATTERNS, RecoilController

    rng = MT19937(42)
    py = RecoilController(PATTERNS["vandal"], rng)
    rs = rs_bridge.RustRecoilController(seed=42)

    schedule = [False] * 2000
    for t in range(10):
        schedule[t] = True
    for t in range(300, 304):
        schedule[t] = True
    for t in range(340, 345):
        schedule[t] = True

    for t in range(2000):
        now = t * DT
        if schedule[t]:
            py.fire(now)
            rs.fire(now)
        py.update(now, DT)
        rs.update(now, DT)
        assert rs.pitch == py.pitch, f"tick {t}: pitch 分歧"
        assert rs.yaw == py.yaw, f"tick {t}: yaw 分歧"
        assert rs.bullet_index == py.bullet_index
        assert rs.shots_fired == py.shots_fired


# --------------------------------------------------------------------- #
# 彈道：Rust 擴展 vs Python（跨發狀態）
# --------------------------------------------------------------------- #
def _ballistic_scene():
    from server.core.math_core import Vec3

    walls = [
        (0.0, 0.0, 4.0, 0.2, 4.0, 4.2, 1),     # wood
        (-2.0, 0.0, 5.0, 2.0, 4.0, 7.0, 0),    # concrete
        (-25.0, 0.0, 19.0, 25.0, 12.0, 20.0, 3),  # unbreakable
    ]
    players = [
        (10.0, 0.0, 0.0, True, 100.0),
        (10.0, 0.0, 8.0, True, 100.0),
        (10.0, 0.0, 6.0, True, 100.0),
        (10.0, 0.0, 21.0, True, 100.0),
    ] + [(50.0, 0.0, 50.0, False, 0.0) for _ in range(6)]
    shots = [
        (0, (10, 1.6, 0), (10, 1.0, 8)),   # vandal 穿木牆打 p1 身
        (0, (10, 1.6, 0), (10, 1.0, 6)),   # vandal 穿木牆打 p2
        (1, (10, 1.6, 0), (10, 1.0, 8)),   # classic 穿不過
        (2, (10, 1.6, 0), (10, 1.0, 21)),  # operator 穿不過 unbreakable
        (0, (10, 1.6, 0), (10, 0.5, 8)),   # 腿（穿牆 0.8×0.85）
        (0, (10, 1.6, 0), (10, 1.8, 8)),   # 爆頭（溢傷）
    ]
    return walls, players, shots


def test_ballistics_rust_matches_python():
    from server.core.math_core import Vec3
    from server.game.ballistics import resolve_hitscan
    from server.game.entities import World
    from server.game.mapdata import MapData, Wall
    from server.game.weapons import weapon

    walls, players, shots = _ballistic_scene()

    # Python 世界
    world = World()
    world.map_data = MapData()
    for (ax, ay, az, bx, by, bz, mat) in walls:
        world.map_data.walls.append(Wall(Vec3(ax, ay, az), Vec3(bx, by, bz),
                                         {0: "concrete", 1: "wood", 3: "unbreakable"}[mat]))
    world.map_data.bounds_min = Vec3(-50, 0, -50)
    world.map_data.bounds_max = Vec3(50, 30, 50)
    for i, (x, y, z, alive, hp) in enumerate(players):
        world.players[i].pos = Vec3(x, y, z)
        world.players[i].alive = alive
        world.players[i].health = hp

    dmg = [40.0, 26.0, 150.0]
    py_results = []
    for wid, origin, target in shots:
        o = Vec3(*origin)
        d = (Vec3(*target) - o).normalized()
        res = resolve_hitscan(world, world.map_data, 0, o, d, weapon(
            ("vandal", "classic", "operator")[wid]), None)
        py_results.append([(h.target_slot, {"head": 0, "body": 1, "legs": 2}[h.region],
                            h.base_damage, h.final_damage, h.penetrated_walls)
                           for h in res.hits])

    # Rust（跨發狀態由呼叫端維護：以 dealt 更新 health/alive）
    rs_players = [list(p) for p in players]
    rs_results = []
    for wid, origin, target in shots:
        hits = rs_bridge.rust_resolve_hitscan(
            [tuple(p) for p in rs_players], walls, 0, origin, target,
            dmg[wid], (2, 0, 2)[wid], 150.0)
        rs_results.append(list(hits))
        for (slot, _r, _b, dealt, _w) in hits:
            rs_players[slot][3] = rs_players[slot][4] > dealt
            rs_players[slot][4] -= dealt
            if rs_players[slot][4] <= 0:
                rs_players[slot][4] = 0.0

    assert rs_results == py_results, f"彈道結果分歧: {rs_results} vs {py_results}"


# --------------------------------------------------------------------- #
# 伺服器整合：換核心前後世界狀態一致
# --------------------------------------------------------------------- #
def test_server_dual_track_identical():
    """同一輸入驅動兩個 World（純 Python vs Rust 移動）→ 逐 tick 狀態一致。"""
    import os as _os

    from server.core.movement import MoveInput

    def run_world(force_py: bool):
        _os.environ["VANTA_FORCE_PY"] = "1" if force_py else "0"
        from server.game.entities import World

        w = World(seed=7)
        w.start_match()
        from server.game.match import RoundPhase

        w.match.phase = RoundPhase.ACTION
        inp = [None] * 10
        inp[0] = MoveInput(forward=1.0)
        inp[1] = MoveInput(strafe=1.0)
        for _ in range(300):
            w.step(inp, DT)
        return [(p.pos.x, p.pos.y, p.pos.z, p.vel.x, p.vel.y, p.vel.z) for p in w.players]

    py_states = run_world(True)
    rs_states = run_world(False)
    assert rs_states == py_states, "Rust 核心與 Python 核心的伺服器狀態分歧"


# --------------------------------------------------------------------- #
# 效能：Rust vs Python（誠實數字）
# --------------------------------------------------------------------- #
def test_rust_movement_faster():
    from server.core.movement import MovementConfig, MovementController, MoveInput

    inputs = _golden_inputs()
    rs = rs_bridge.RustMovementController(MovementConfig(), 0.0)
    py = MovementController(MovementConfig(), 0.0)
    # 熱身
    for i in inputs:
        rs.step(i, DT)
        py.step(i, DT)
    import time

    reps = 3
    t0 = time.perf_counter()
    for _ in range(reps):
        c = rs_bridge.RustMovementController(MovementConfig(), 0.0)
        for i in inputs:
            c.step(i, DT)
    rs_t = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(reps):
        c = MovementController(MovementConfig(), 0.0)
        for i in inputs:
            c.step(i, DT)
    py_t = time.perf_counter() - t0
    assert rs_t < py_t, f"Rust 未更快: rs={rs_t:.3f}s py={py_t:.3f}s"
    # 記錄加速比（不設過嚴斷言，避免 CI 波動）
    print(f"\n[bench] Rust {rs_t:.3f}s vs Python {py_t:.3f}s → {py_t / max(rs_t, 1e-9):.1f}x")
