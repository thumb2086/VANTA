"""
M1 角色移動控制器 + 移動準度懲罰 單元測試。

驗證重點：
  1. 三種姿態（跑/靜步/蹲）的最大速度與「斜向不超速」
  2. 反切 (Counter-Strafe) 急停比純摩擦快 → 對齊 FPS 手感
  3. 跳躍拋物線：最高點 = v²/2g、總滯空 ≈ 2v/g、不可空中二段跳
  4. 確定性：相同輸入序列 → 位元級相同輸出
  5. 移動準度懲罰：靜止 0 / 跑步最大 / 靜步一半 / 蹲走更小 / 空中更糟 / 落地衰減
"""

import math

from server.core.accuracy import MovementErrorEngine
from server.core.movement import MoveInput, MovementConfig, MovementController

DT = 1.0 / 128.0          # 伺服器 tick 間隔（128 Hz）
CFG = MovementConfig()    # 預設參數：run 5.4 / jump 4.6 / g 11.5 ...


def run_for(ctrl: MovementController, inp: MoveInput, seconds: float) -> MovementController:
    """以固定 dt 模擬 seconds 秒。"""
    for _ in range(int(round(seconds / DT))):
        ctrl.step(inp, DT)
    return ctrl


# --------------------------------------------------------------------- #
# 1. 姿態與速度
# --------------------------------------------------------------------- #
def test_stays_still_when_no_input():
    c = MovementController()
    run_for(c, MoveInput(), 1.0)
    assert c.pos == c.pos.__class__(0.0, 0.0, 0.0)
    assert c.vel == c.vel.__class__()
    assert c.on_ground


def test_run_reaches_max_speed():
    c = MovementController()
    run_for(c, MoveInput(forward=1.0), 1.0)
    assert math.isclose(c.horizontal_speed(), 5.4, rel_tol=1e-6)
    # 1 秒位移 ≈4.75 m：加速段 ~245ms（特戰手感）後滿速
    assert 4.5 < c.pos.z < 5.2


def test_walk_speed_is_54_percent():
    c = MovementController()
    run_for(c, MoveInput(forward=1.0, walk=True), 0.5)
    assert math.isclose(c.horizontal_speed(), 5.4 * 0.54, rel_tol=1e-6)


def test_crouch_speed_is_43_percent():
    c = MovementController()
    run_for(c, MoveInput(forward=1.0, crouch=True), 0.5)
    assert math.isclose(c.horizontal_speed(), 5.4 * 0.43, rel_tol=1e-6)


def test_speed_hierarchy_run_walk_crouch():
    run, walk, crouch = [], [], []
    for kind in ("run", "walk", "crouch"):
        c = MovementController()
        inp = MoveInput(forward=1.0, walk=(kind == "walk"), crouch=(kind == "crouch"))
        run_for(c, inp, 0.5)
        (run if kind == "run" else walk if kind == "walk" else crouch).append(c.horizontal_speed())
    assert crouch[0] < walk[0] < run[0]


def test_diagonal_input_no_overspeed():
    """斜向（W+D）速度不得超過直線跑速（對角線校正）。"""
    c = MovementController()
    run_for(c, MoveInput(forward=1.0, strafe=1.0), 0.5)
    assert c.horizontal_speed() <= 5.4 + 1e-9
    assert c.pos.x > 1.0 and c.pos.z > 1.0   # 兩個方向都有位移


# --------------------------------------------------------------------- #
# 2. 反切急停
# --------------------------------------------------------------------- #
def test_counter_strafe_stops_faster_than_friction():
    def time_to_stop(use_opposite: bool) -> float:
        c = MovementController()
        run_for(c, MoveInput(strafe=1.0), 0.5)          # 加速到全速向右
        assert c.horizontal_speed() > 5.3
        inp = MoveInput(strafe=-1.0) if use_opposite else MoveInput()
        t = 0.0
        for _ in range(600):
            c.step(inp, DT)
            t += DT
            if c.horizontal_speed() < 0.2:              # 視為「急停完成」
                return t
        return 999.0

    counter = time_to_stop(True)
    friction = time_to_stop(False)
    assert counter < friction * 0.6       # 反切明顯快於純摩擦
    assert counter < 0.20                 # ≈120ms（特戰 ~100-150ms）
    assert friction < 0.40                # ≈220ms 滑停（有慣性承諾感）


# --------------------------------------------------------------------- #
# 3. 跳躍
# --------------------------------------------------------------------- #
def test_jump_kinematics():
    """最高點 ≈ v²/2g = 0.75m（特戰實測）；總滯空 ≈ 2v/g ≈ 0.72s。"""
    c = MovementController()
    c.step(MoveInput(jump=True), DT)
    assert not c.on_ground

    max_y, land_tick = 0.0, None
    for i in range(300):
        c.step(MoveInput(), DT)
        max_y = max(max_y, c.pos.y)
        if land_tick is None and c.on_ground:
            land_tick = i

    apex_expected = CFG.jump_speed**2 / (2 * CFG.gravity)
    airtime_expected = 2 * CFG.jump_speed / CFG.gravity
    assert math.isclose(max_y, apex_expected, rel_tol=0.05)
    assert land_tick is not None
    assert math.isclose((land_tick + 1) * DT, airtime_expected, rel_tol=0.06)
    assert c.on_ground


def test_gravity_applied_while_airborne():
    c = MovementController()
    c.step(MoveInput(jump=True), DT)
    vy_after_launch = c.vel.y
    c.step(MoveInput(), DT)
    assert math.isclose(c.vel.y, vy_after_launch - CFG.gravity * DT, rel_tol=1e-9)


def test_no_mid_air_jump():
    """空中按跳無效：不會重置垂直速度。"""
    c = MovementController()
    c.step(MoveInput(jump=True), DT)
    for _ in range(30):                       # ≈0.23s 後仍在空中（滯空 0.8s）
        c.step(MoveInput(), DT)
    assert not c.on_ground
    vy_before = c.vel.y
    c.step(MoveInput(jump=True), DT)          # 空中按跳
    assert math.isclose(c.vel.y, vy_before - CFG.gravity * DT, rel_tol=1e-9)
    assert not c.on_ground


def test_jump_buffer_works_on_ground():
    """落地前 0.1s 內按跳（緩衝）→ 落地瞬間自動起跳。"""
    c = MovementController()
    c.step(MoveInput(jump=True), DT)
    # 在空中按住 jump 直到落地：緩衝會讓角色落地後立刻再跳一次
    for _ in range(150):
        c.step(MoveInput(jump=True), DT)
    assert not c.on_ground                     # 仍在跳躍中


# --------------------------------------------------------------------- #
# 4. 確定性
# --------------------------------------------------------------------- #
def test_determinism_same_input_same_state():
    inputs = (
        [MoveInput(strafe=1.0)] * 50
        + [MoveInput(strafe=-1.0, walk=True)] * 60
        + [MoveInput(jump=True)]
        + [MoveInput(forward=1.0, crouch=True)] * 100
    )
    a, b = MovementController(), MovementController()
    for inp in inputs:
        a.step(inp, DT)
        b.step(inp, DT)
    assert a.pos == b.pos          # 位元級相等
    assert a.vel == b.vel
    assert a.on_ground == b.on_ground


# --------------------------------------------------------------------- #
# 5. 移動準度懲罰 (Movement Penalty)
# --------------------------------------------------------------------- #
def test_error_standing_still_is_zero():
    eng = MovementErrorEngine()
    c = MovementController()
    assert eng.error_for(c, "rifle") == 0.0


def test_error_running_is_class_max():
    eng = MovementErrorEngine()
    assert eng.error_deg(1.0, False, False, False, 999.0, "rifle") == 2.4


def test_error_walk_is_half():
    eng = MovementErrorEngine()
    assert eng.error_deg(1.0, True, False, False, 999.0, "rifle") == 1.2


def test_error_crouch_walk_smaller_than_walk():
    eng = MovementErrorEngine()
    crouch = eng.error_deg(1.0, False, True, False, 999.0, "rifle")
    walk = eng.error_deg(1.0, True, False, False, 999.0, "rifle")
    assert crouch < walk
    assert math.isclose(crouch, 2.4 * 0.35, rel_tol=1e-9)


def test_error_airborne_worse_than_running():
    eng = MovementErrorEngine()
    air = eng.error_deg(0.0, False, False, True, 999.0, "rifle")
    assert air == 2.4 * 1.25
    assert air > 2.4


def test_error_scales_with_speed():
    eng = MovementErrorEngine()
    half = eng.error_deg(0.5, False, False, False, 999.0, "rifle")
    assert math.isclose(half, 2.4 * 0.5, rel_tol=1e-9)


def test_land_penalty_decays_over_time():
    eng = MovementErrorEngine()
    err0 = eng.error_deg(0.0, False, False, False, 0.0, "rifle")        # 剛落地
    err_mid = eng.error_deg(0.0, False, False, False, 0.113, "rifle")   # 過半
    err_done = eng.error_deg(0.0, False, False, False, 0.3, "rifle")    # 已結束
    assert math.isclose(err0, 7.0, rel_tol=1e-9)
    assert 0.0 < err_mid < 7.0
    assert err_done == 0.0


def test_integration_error_right_after_landing():
    """落地瞬間誤差 = 7°，0.3s 後回到 0。"""
    eng = MovementErrorEngine()
    c = MovementController()
    c.step(MoveInput(jump=True), DT)
    for _ in range(300):
        c.step(MoveInput(), DT)
        if c.on_ground:
            break
    assert c.on_ground
    assert c.time_since_land == 0.0
    assert eng.error_for(c, "rifle") == 7.0
    for _ in range(int(0.3 / DT)):
        c.step(MoveInput(), DT)
    assert eng.error_for(c, "rifle") == 0.0
