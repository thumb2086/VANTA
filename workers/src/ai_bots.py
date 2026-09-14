"""
workers/src/ai_bots.py — AI 機器人邏輯（移植自 scripts/demo_match.py）
=====================================================================
供觀戰/示範模式：空槽位由 AI 補位。邏輯與 demo_match 一致：
購買期買甲買槍；行動期衝 A 點安放 / 守點 / 回防拆除 / 近距交戰急停。
"""

from __future__ import annotations

import math

from server.core.math_core import Vec3, clamp
from server.core.movement import MoveInput
from server.game.match import TEAM_ATTACKERS, TEAM_DEFENDERS

A_SITE = Vec3(12, 0, 10)
# VANTA-1 A 點守備位（gen 後 / Tree 側 / 後站 / 半牆後 / 包點北）
DEFENDER_HOLDS = [Vec3(12, 0, 6.8), Vec3(9.5, 0, 9.3), Vec3(15.5, 0, 12.5),
                  Vec3(17.5, 0, 11.5), Vec3(12.5, 0, 12.8)]

# 8 方向候選（牆壁感知貪婪尋路）
_CANDIDATES = (
    (0.0, 1.0), (0.7071, 0.7071), (1.0, 0.0), (0.7071, -0.7071),
    (0.0, -1.0), (-0.7071, -0.7071), (-1.0, 0.0), (-0.7071, 0.7071),
)


def steer_toward(world, pos, target, max_sight: float = 14.0, prev=None) -> MoveInput:
    """牆壁感知：直線可達 → 直走；被擋 → 8 方向挑「朝目標進展 × 可達性」最佳。"""
    eye = pos + Vec3(0, 1.6, 0)
    to_target = target - pos
    dist = to_target.length()
    if dist < 0.5:
        return MoveInput()
    dn = to_target.normalized()
    if world.map_data.los_clear(eye, eye + dn * min(dist, max_sight)):
        return MoveInput(forward=clamp(dn.z, -1, 1), strafe=clamp(dn.x, -1, 1))
    cands = [Vec3(dx, 0, dz).normalized() for dx, dz in _CANDIDATES]
    if prev is not None:
        cands.append(prev)
    best = None
    for cand in cands:
        hit = world.map_data.raycast(eye, cand, max_sight)
        reach = hit.dist if hit is not None else max_sight
        prog = max(0.0, cand.dot(dn))
        score = prog * (reach / max_sight) + reach * 0.01
        if best is None or score > best[0]:
            best = (score, cand)
    if best is None:
        return MoveInput()
    c = best[1]
    return MoveInput(forward=clamp(c.z, -1, 1), strafe=clamp(c.x, -1, 1))


_prev_dir: dict = {}

# AI 決策節流：每 4 tick（32Hz）重新決策，其餘 tick 沿用 — 效能關鍵
_AI_DECIDE_INTERVAL = 4
_bot_inputs: dict = {}


def decide_bots(world, match) -> dict:
    """每 tick 呼叫：節流決策並回傳此 tick 的 AI 輸入表（無 Session 槽位用）。"""
    if world.tick % _AI_DECIDE_INTERVAL != 0:
        return _bot_inputs
    out: dict = {}
    for i in range(10):
        m = bot_act(world, i)
        if m is not None:
            out[i] = m
    _bot_inputs.update(out)
    return _bot_inputs


def nearest_enemy(world, slot):
    p = world.players[slot]
    best, best_d = None, 1e9
    for i, q in enumerate(world.players):
        if i == slot or not q.alive or q.team == p.team:
            continue
        d = p.pos.distance_to(q.pos)
        if d < best_d:
            best, best_d = i, d
    return best, best_d


# ── 難度參數（讓 AI 有人性：不會零反應 + 百發百中）──────────────
BOT_REACTION_S = 0.4          # 看到敵人後的反應延遲（人類水準）
BOT_AIM_ERROR_BASE_DEG = 2.0  # 瞄準誤差基準（近距離）
BOT_AIM_ERROR_PER_M = 0.25    # 每公尺額外誤差
BOT_BURST_MAX = 5             # 單次連射發數（之後停火休息）
BOT_BURST_PAUSE_S = 0.55      # 連射後停火時間
BOT_OPENING_HOLD_S = 2.5      # 開局先在出生區等 2.5 秒再推進

# 確定性 RNG：固定種子 → 同一場比賽的 AI 決策位元級可重放
# （原本用全域 random，破壞「錄製→重放位元級一致」的專案承諾）
_rng = __import__("random").Random(20240614)

# 每槽位 AI 狀態（反應計時/連射計數/開局延遲）
_bot_state: dict = {}


def _st(slot):
    return _bot_state.setdefault(slot, {
        "seen_at": None,      # 第一次看到敵人的世界時間
        "burst": 0,
        "pause_until": 0.0,
        "opening_until": None,
    })


def try_shoot(world, slot, enemy, now):
    """瞄準射擊（含反應延遲 + 瞄準誤差 + 連射節奏）。回傳是否看得到敵人。"""
    st = _st(slot)
    p = world.players[slot]
    q = world.players[enemy]
    eye = p.pos + Vec3(0, 1.6, 0)
    tgt = q.pos + Vec3(0, 1.0, 0)
    if not world.map_data.los_clear(eye, tgt):
        st["seen_at"] = None            # 失去視線 → 重新計反應
        return False
    if st["seen_at"] is None:
        st["seen_at"] = now
    if now - st["seen_at"] < BOT_REACTION_S:
        return True                     # 還在反應中（不開火）
    if now < st["pause_until"]:
        return True                     # 連射後的停火休息
    aim = (tgt - eye).normalized()
    # 瞄準誤差（距離越遠越歪；確定性 RNG）
    dist = p.pos.distance_to(q.pos)
    err = BOT_AIM_ERROR_BASE_DEG + dist * BOT_AIM_ERROR_PER_M
    yaw_err = _rng.uniform(-err, err)
    pitch_err = _rng.uniform(-err, err)
    yaw = math.degrees(math.atan2(aim.x, aim.z)) - p.weapon.aim_yaw_offset + yaw_err
    pitch = math.degrees(math.asin(clamp(aim.y, -1, 1))) - p.weapon.aim_pitch_offset + pitch_err
    world.fire_shot(slot, yaw, pitch)
    st["burst"] += 1
    if st["burst"] >= BOT_BURST_MAX:
        st["burst"] = 0
        st["pause_until"] = now + BOT_BURST_PAUSE_S
    return True


def bot_act(world, slot):
    p = world.players[slot]
    if not p.alive:
        return None
    match = world.match
    phase = match.phase.value

    # --- 購買期 ---
    if phase != "action":
        if p.shield_hp <= 0 and p.economy.credits >= 1000:
            p.buy_shield(2)                    # 重甲
        if p.weapon.stats.key == "classic" and p.economy.credits >= 3900:
            p.buy_weapon("vandal")             # 步槍 + 甲
        return MoveInput()

    # --- 行動期 ---
    spike = world.spike
    is_attacker = p.team == TEAM_ATTACKERS
    enemy, dist = nearest_enemy(world, slot)
    st = spike.state.value if spike is not None else "idle"
    now = world.time

    # 開局緩衝：行動期前幾秒先整備（攻方不搶跑、守方卡位）→ 人類有反應時間
    sts = _st(slot)
    if sts.get("opening_round") != match.round:
        from server.game.match import ACTION_TIME

        sts["opening_round"] = match.round
        action_start = world.time - max(0.0, ACTION_TIME - match.phase_timer)
        sts["opening_until"] = action_start + BOT_OPENING_HOLD_S
        sts["seen_at"] = None
    if now < sts["opening_until"]:
        return MoveInput()

    # Spike 互動（安放 / 拆除）
    if spike is not None:
        if is_attacker and st == "idle" and p.pos.distance_to(A_SITE) <= 2.5:
            spike.set_hold_plant(slot, True)
            return MoveInput()
        if not is_attacker and st == "planted" and p.pos.distance_to(spike._spike_pos()) <= 2.0:
            spike.set_hold_defuse(slot, True)
            return MoveInput()

    # 目標選擇
    if is_attacker:
        if st == "planted":
            target = world.players[enemy].pos if enemy is not None else A_SITE
        else:
            target = A_SITE
    else:
        if st == "planted":
            target = spike._spike_pos()
        elif enemy is not None and dist <= 20.0:
            target = world.players[enemy].pos
        else:
            target = DEFENDER_HOLDS[slot - 5]

        # 攻方執行安放：離 A 點 12m 內 → 無視交戰、直奔點位
    if is_attacker and st == "idle" and p.pos.distance_to(A_SITE) <= 12.0:
        m = steer_toward(world, p.pos, A_SITE, prev=_prev_dir.get(slot))
        _prev_dir[slot] = Vec3(m.strafe, 0, m.forward)
        return m

    # 移動向量
    m = steer_toward(world, p.pos, target, prev=_prev_dir.get(slot))
    _prev_dir[slot] = Vec3(m.strafe, 0, m.forward)
    move = m

    # 射擊：≤8m 視線清晰 → 急停開火；8–25m → 移動中壓制
    if enemy is not None and dist <= 25.0:
        visible = try_shoot(world, slot, enemy, now)
        if visible and dist <= 8.0:
            return MoveInput()
        if not visible and dist <= 8.0:
            return move
    return move
