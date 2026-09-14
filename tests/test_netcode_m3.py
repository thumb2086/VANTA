"""
M3 同步三兄弟測試：
  1. 客戶端預測 —— 相同設定下，預測狀態與伺服器一致（無需校正）
  2. 伺服器和解 —— 客戶端設定偏差時，被快照校正並收斂
  3. Rollback 延遲補償 —— 100ms 延遲下射擊「所見」位置命中；
     對照組（目前位置）落空
"""

import math

import pytest

from server.core.math_core import Vec3, yaw_pitch_from_dir
from server.core.movement import MovementConfig, MovementController, MoveInput
from server.game.entities import World
from server.game.weapons import weapon
from server.game.ballistics import resolve_hitscan
from server.netcode.client_loop import GameClient
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1.0 / 128.0


def build_pair(latency=0.05, seed=1, c0_cfg=None):
    """射手 c0 + 目標 c1。"""
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=seed)
    world = World()
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    sim.set_link("server", "c0", latency=latency)
    sim.set_link("server", "c1", latency=latency)
    walls = [(w.mn, w.mx) for w in world.map_data.walls]
    c0 = GameClient(transport=sim.create_endpoint("c0"), server_addr="server", clock=clock,
                    move_cfg=c0_cfg, walls=walls)
    c1 = GameClient(transport=sim.create_endpoint("c1"), server_addr="server", clock=clock,
                    walls=walls)
    return clock, sim, server, c0, c1


def run(clock, sim, server, clients, inputs, ticks):
    for t in range(ticks):
        for c in clients:
            c.poll()
        for c, inp in zip(clients, inputs):
            if inp is not None:
                c.send_input(inp)
        clock.advance(DT)
        sim.flush()
        server.step(DT)


# --------------------------------------------------------------------- #
# 1. 客戶端預測一致
# --------------------------------------------------------------------- #
def test_prediction_matches_server_no_correction():
    # 零延遲：伺服器與客戶端看到完全相同的輸入序列 → 預測一致、無需校正
    clock, sim, server, c0, c1 = build_pair(latency=0.0, seed=2)
    # 客戶端預測控制器以「出生點」起算（真實客戶端由首張快照種子化，
    # 此處直接設定 → 排除「出生點對齊」這 2 次必然校正）；
    # 伺服器端同步設到同點，VANTA-1 攻方出生 (-6,-16.5)
    start = Vec3(-6, 0, -16.5)
    server.world.players[0].pos = Vec3(start.x, 0, start.z)
    c0.local.pos = start
    run(clock, sim, server, [c0, c1],
        [MoveInput(forward=1.0), MoveInput(strafe=1.0)], 300)

    snap = c0.last_snapshot
    assert snap is not None
    e = snap.state_for_slot(0)
    assert e is not None and e.occupied
    # 對應到「伺服器已確認 seq」的預測位置 → 與伺服器位置一致（量化誤差內）
    if e.last_input_seq in c0.predicted:
        pp = c0.predicted[e.last_input_seq][0]
        assert pp.distance_to(e.pos) < 0.05
    assert c0.reconcile_count == 0          # 輸入序列一致 → 無需校正


def test_prediction_is_ahead_of_server_state():
    """預測的本意：本地位置領先伺服器（約一個 RTT）。"""
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=3)
    world = World()
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    sim.set_link("server", "c0", latency=0.1)
    sim.set_link("server", "c1", latency=0.1)
    walls = [(w.mn, w.mx) for w in world.map_data.walls]
    c0 = GameClient(transport=sim.create_endpoint("c0"), server_addr="server", clock=clock,
                    walls=walls)
    c1 = GameClient(transport=sim.create_endpoint("c1"), server_addr="server", clock=clock,
                    walls=walls)
    run(clock, sim, server, [c0, c1],
        [MoveInput(forward=1.0), MoveInput()], 300)
    # 客戶端本地領先伺服器（c0 由出生點起跑）
    local_z = c0.local.pos.z
    server_z = server.world.players[0].pos.z
    assert local_z > server_z + 0.2         # 領先 > 0.2m
    assert server_z > -11.0                 # 確實有在跑


# --------------------------------------------------------------------- #
# 2. 伺服器和解
# --------------------------------------------------------------------- #
def test_reconciliation_corrects_drift():
    # 客戶端用錯誤設定（較慢跑速）→ 預測與伺服器分歧 → 被校正
    bad_cfg = MovementConfig(run_speed=5.0)     # 伺服器是 5.4
    clock, sim, server, c0, c1 = build_pair(latency=0.05, seed=4, c0_cfg=bad_cfg)
    run(clock, sim, server, [c0, c1],
        [MoveInput(forward=1.0), MoveInput()], 400)

    assert c0.reconcile_count > 0
    # 最終本地狀態收斂到伺服器（誤差 < 1 個框架的距離）
    assert c0.local.pos.distance_to(server.world.players[0].pos) < 0.3


def test_reconcile_keeps_sim_consistent():
    """校正後，重放輸入依然產生合法狀態（不超速、不穿地）。"""
    bad_cfg = MovementConfig(gravity=20.0)      # 重力異常大
    clock, sim, server, c0, c1 = build_pair(latency=0.03, seed=5, c0_cfg=bad_cfg)
    run(clock, sim, server, [c0, c1],
        [MoveInput(forward=1.0, jump=True)] * 0 + [MoveInput(forward=1.0)], 300)
    assert c0.local.pos.y >= -0.01
    assert c0.local.horizontal_speed() <= 5.4 + 0.05


# --------------------------------------------------------------------- #
# 3. Rollback 延遲補償
# --------------------------------------------------------------------- #
def test_rollback_hit_registration():
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=6)
    world = World()
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[0].pos = Vec3(-8, 0, 0)       # 射手站定（開闊處）
    world.players[1].pos = Vec3(-8, 0, 8)       # 目標在前方
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    sim.set_link("server", "c0", latency=0.1)
    sim.set_link("server", "c1", latency=0.1)
    walls = [(w.mn, w.mx) for w in world.map_data.walls]
    c0 = GameClient(transport=sim.create_endpoint("c0"), server_addr="server", clock=clock,
                    walls=walls)
    c1 = GameClient(transport=sim.create_endpoint("c1"), server_addr="server", clock=clock,
                    walls=walls)

    # 暖機：目標向 +X 橫向移動（垂直於視線）
    for _ in range(240):
        c0.poll(); c1.poll()
        c0.send_input(MoveInput())
        c1.send_input(MoveInput(strafe=1.0))
        clock.advance(DT); sim.flush(); server.step(DT)

    # 射手瞄準「所見快照」中目標的位置（延遲 0.1s → 目標其實已向前 0.54m）
    snap = c0.last_snapshot
    e_target = snap.state_for_slot(1)
    assert e_target is not None and e_target.occupied
    eye = c0.local.pos + Vec3(0, 1.6, 0)
    # 瞄準「所見」目標的胸口（腳底上方 1.0m，避開射線穿過腳底的膠囊盲區）
    aim_dir = (e_target.pos + Vec3(0, 1.0, 0)) - eye
    yaw, pitch = yaw_pitch_from_dir(aim_dir)
    fired_seq = c0.snapshot_echo_seq()
    assert fired_seq is not None

    # 對照組（無補償）：同瞄點、以「目前位置」判定 → 應落空
    origin_now = server.world.players[0].pos + Vec3(0, 1.6, 0)
    res_now = resolve_hitscan(world, world.map_data, 0, origin_now,
                              aim_dir.normalized(), weapon("classic"), None)
    assert res_now.hits == []

    # 開火（附帶 Rollback seq）；等封包穿越 0.1s×2 延遲到達伺服器並處理
    c0.send_shot(yaw, pitch, fired_seq)
    for _ in range(40):
        c0.poll(); c1.poll()
        c0.send_input(MoveInput())
        c1.send_input(MoveInput(strafe=1.0))
        clock.advance(DT); sim.flush(); server.step(DT)

    # 補償後 → 命中，目標受傷（甚至死亡）
    target = server.world.players[1]
    assert target.health < 100.0
    assert not target.alive or target.health < 100.0


def test_rollback_hits_at_multiple_latencies():
    for latency in (0.05, 0.1, 0.2):
        clock = VirtualClock()
        sim = NetworkSimulator(clock=clock, seed=6)
        world = World()
        world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
        world.players[0].pos = Vec3(-8, 0, 0)
        world.players[1].pos = Vec3(-8, 0, 8)
        # 無關玩家移出彈道（否則對照組的「必落空」斷言會被旁觀者干擾）
        for i in range(2, 10):
            world.players[i].pos = Vec3(0, -50, 0)
        server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
        sim.set_link("server", "c0", latency=latency)
        sim.set_link("server", "c1", latency=latency)
        walls = [(w.mn, w.mx) for w in world.map_data.walls]
        c0 = GameClient(transport=sim.create_endpoint("c0"), server_addr="server", clock=clock,
                        walls=walls)
        c1 = GameClient(transport=sim.create_endpoint("c1"), server_addr="server", clock=clock,
                        walls=walls)
        # 快照 16Hz：開火緊跟在收到快照之後（age 最小化），
        # 原始快照位置即回滾目標——直接瞄準即可驗證補償正確性
        for _ in range(240):
            c0.poll(); c1.poll()
            c0.send_input(MoveInput())
            c1.send_input(MoveInput(strafe=1.0))
            clock.advance(DT); sim.flush(); server.step(DT)
        e_target = c0.last_snapshot.state_for_slot(1)
        eye = c0.local.pos + Vec3(0, 1.6, 0)
        aim = (e_target.pos + Vec3(0, 1.0, 0)) - eye
        yaw, pitch = yaw_pitch_from_dir(aim)
        c0.send_shot(yaw, pitch, c0.snapshot_echo_seq())
        for _ in range(60):                       # 等封包穿越 2×latency 並被處理
            c0.poll(); c1.poll()
            c0.send_input(MoveInput())
            c1.send_input(MoveInput(strafe=1.0))
            clock.advance(DT); sim.flush(); server.step(DT)
        # 補償後命中
        assert server.world.players[1].health < 100.0, f"latency={latency}"
        # 無補償對照必定落空（目前位置橫移 0.27/0.54/1.08m）
        origin_now = server.world.players[0].pos + Vec3(0, 1.6, 0)
        res = resolve_hitscan(world, world.map_data, 0, origin_now,
                              aim.normalized(), weapon("classic"), None)
        assert res.hits == [], f"latency={latency}"
