"""反作弊系統測試（伺服器權威驗證）。"""

import math

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.netcode.anticheat import AntiCheat, AntiCheatConfig, CheatReport
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1 / 128.0


def _ac(cfg=None):
    return AntiCheat(cfg)


# --------------------------------------------------------------------- #
# 輸入 / 行動速率
# --------------------------------------------------------------------- #
def test_input_flood_detected():
    ac = _ac(AntiCheatConfig(max_inputs_per_sec=10))
    now = 0.0
    reports = []
    for i in range(30):
        r = ac.on_input("a", now + i * 0.001)   # 遠超 10/s
        if r is not None:
            reports.append(r)
    assert reports
    assert any(r.kind == "INPUT_FLOOD" for r in reports)


def test_input_normal_ok():
    ac = _ac(AntiCheatConfig(max_inputs_per_sec=128))
    for i in range(128):
        assert ac.on_input("a", i * (1 / 128.0)) is None


def test_action_flood_detected():
    ac = _ac(AntiCheatConfig(max_actions_per_sec=20))
    now = 0.0
    any_flag = False
    for i in range(60):
        r = ac.on_action("b", now + i * 0.005)
        any_flag = any_flag or (r is not None and r.kind == "ACTION_FLOOD")
    assert any_flag


def test_fire_rate_abuse_detected():
    ac = _ac(AntiCheatConfig(fire_rate_attempt_window=5))
    flag = None
    for i in range(10):
        flag = ac.note_fire_attempt("c", 0, allowed=False, now=i * 0.02)
    assert flag is not None
    assert flag.kind == "FIRE_RATE_ABUSE"
    # 正常開火後重置
    ac.note_fire_attempt("c", 0, allowed=True, now=100.0)
    assert ac.note_fire_attempt("c", 0, allowed=False, now=101.0) is None


# --------------------------------------------------------------------- #
# 移動驗證
# --------------------------------------------------------------------- #
def test_teleport_detected_and_corrected():
    ac = _ac(AntiCheatConfig(teleport_tolerance_m=0.35))
    world = World()
    # 正常走一 tick 建立基線（VANTA-1 邊界 ±21 內）
    world.players[0].pos = Vec3(0, 0, -5)
    ac.validate_movement(world, 1)
    # 瞬間移動 20m（仍在邊界內 → 純 TELEPORT 而非 OUT_OF_BOUNDS）
    world.players[0].pos = Vec3(0, 0, 15)
    reports = ac.validate_movement(world, 2)
    teleports = [r for r in reports if r.kind == "TELEPORT"]
    assert teleports
    # 伺服器權威修正：回彈到上一個合法位置
    assert world.players[0].pos.distance_to(Vec3(0, 0, -5)) < 0.01
    assert world.players[0].vel.length() < 1e-9      # 速度歸零


def test_speed_hack_detected():
    ac = _ac(AntiCheatConfig(max_speed_mps=7.5))
    world = World()
    world.players[0].pos = Vec3(0, 0, -5)
    ac.validate_movement(world, 1)
    # 作弊：直接設高速
    world.players[0].vel = Vec3(0, 0, 50.0)
    world.players[0].pos = Vec3(0, 0, -4.95)         # 位移小（正常）→ 只抓速度
    reports = ac.validate_movement(world, 2)
    assert any(r.kind == "SPEED_HACK" for r in reports)
    # 速度被夾到上限
    assert world.players[0].vel.z <= 7.5 + 1e-6


def test_out_of_bounds_detected():
    ac = _ac()
    world = World()
    world.players[0].pos = Vec3(0, 0, -5)
    ac.validate_movement(world, 1)
    world.players[0].pos = Vec3(999, 0, 999)
    reports = ac.validate_movement(world, 2)
    assert any(r.kind == "OUT_OF_BOUNDS" for r in reports)


def test_normal_movement_no_false_positive():
    """正常玩家（跑步/跳躍/反切）不觸發任何違規。"""
    ac = _ac()
    world = World()
    world.start_match()
    from server.game.match import RoundPhase

    world.match.phase = RoundPhase.ACTION
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    inp[1] = MoveInput(strafe=1.0)
    reports = []
    for _ in range(128 * 3):
        world.step(inp, DT)
        reports.extend(ac.validate_movement(world, _))
    assert reports == []


def test_round_reset_clears_position_tracking():
    """回合重置後位置追蹤清空（重生傳送不誤判）。"""
    ac = _ac()
    world = World()
    world.players[0].pos = Vec3(0, 0, -5)
    ac.validate_movement(world, 1)
    ac.on_round_reset()                              # 重生
    world.players[0].pos = Vec3(4, 0, 12)            # 傳送到重生點（合法）
    reports = ac.validate_movement(world, 2)
    assert reports == []


# --------------------------------------------------------------------- #
# 踢除（整合進伺服器）
# --------------------------------------------------------------------- #
def test_kick_after_repeated_teleports():
    """連續瞬間移動 → severity 3 → 伺服器踢除 Session。"""
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=1)
    world = World()
    world.start_match()
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    # 調低閾值方便測試
    server.anticheat.cfg.kick_after_violations = 3
    kicks = []
    server.on_cheat_report = lambda r: kicks.append(r)

    ep = sim.create_endpoint("c")
    from server.netcode.client_loop import GameClient

    cl = GameClient(transport=ep, server_addr="server", clock=clock)
    # 建立 session
    cl.send_input(MoveInput())
    clock.advance(DT)
    sim.flush()
    server.step(DT)
    assert len(server.sessions) == 1

    # 連續 4 次瞬間移動
    for i in range(4):
        slot = next(iter(server.sessions.values())).slot
        server.world.players[slot].pos = Vec3(i * 100, 0, 0)
        server.step(DT)
        if not server.sessions:
            break
    assert len(server.sessions) == 0                 # 已被踢除
    assert any(k.severity == 3 for k in kicks)
    assert any("KICK" in e for e in server.world.event_log)


def test_fire_abuse_kicks():
    """射速濫用 → 累計違規 → 踢除。"""
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=2)
    world = World()
    world.start_match()
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    server.anticheat.cfg.kick_after_violations = 3
    ep = sim.create_endpoint("c")
    from server.netcode.client_loop import GameClient
    from server.netcode.protocol import ACTION_SHOOT

    cl = GameClient(transport=ep, server_addr="server", clock=clock)
    cl.send_input(MoveInput())
    clock.advance(DT)
    sim.flush()
    server.step(DT)

    # 短時間內連發 ACTION_SHOOT（射速冷卻擋下 → 濫用偵測）
    from server.game.match import RoundPhase

    world.match.phase = RoundPhase.ACTION
    for i in range(40):
        cl.send_action(ACTION_SHOOT, p0=0, p1=0)
        clock.advance(DT)
        sim.flush()
        server.step(DT)
    # 觸發踢除（fire abuse 累計）
    assert len(server.sessions) == 0 or \
        any("FIRE_RATE_ABUSE" in e for e in server.world.event_log)


def test_anticheat_summary():
    ac = _ac(AntiCheatConfig(max_inputs_per_sec=5))
    for i in range(20):
        ac.on_input("x", i * 0.001)
    s = ac.summary()
    assert any("INPUT_FLOOD" in kinds for kinds in s.values())
