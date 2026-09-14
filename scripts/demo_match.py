"""
scripts/demo_match.py — 全自動 AI 對戰示範
==========================================
以「伺服器權威世界」直接驅動 5v5 AI 打一整場比賽，展示全系統：
  移動 + 碰撞 + 射擊（移動準度懲罰 + 急停）+ 經濟購買 + Spike 安放/拆除/爆炸
  + 回合狀態機。

執行：python3 scripts/demo_match.py
"""

from __future__ import annotations

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from server.core.math_core import Vec3, clamp
from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase, TEAM_ATTACKERS, TEAM_DEFENDERS

DT = 1.0 / 128.0
A_SITE = Vec3(12, 0, 10)
MAX_TICKS = 128 * 420          # 最多模擬 420 秒

# 守方卡點（A 點周邊：守點不追擊 → 攻方執行安放後，守方回防拆除）
DEFENDER_HOLDS = [Vec3(7, 0, 7), Vec3(9, 0, 8), Vec3(11, 0, 8), Vec3(8, 0, 10), Vec3(11, 0, 11)]


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


def try_shoot(world, slot, enemy):
    """若視線清晰 → 開火。回傳是否看得到敵人。

    後座力補償：fire_shot 會把「累積後座力偏移」疊加到瞄準角（模擬槍口上揚），
    因此開火前要抵銷它——這就是真實玩家「下拉滑鼠壓槍」的動作。
    """
    p = world.players[slot]
    q = world.players[enemy]
    eye = p.pos + Vec3(0, 1.6, 0)
    tgt = q.pos + Vec3(0, 1.0, 0)
    if not world.map_data.los_clear(eye, tgt):
        return False
    aim = (tgt - eye).normalized()
    yaw = math.degrees(math.atan2(aim.x, aim.z)) - p.weapon.aim_yaw_offset
    pitch = math.degrees(math.asin(clamp(aim.y, -1, 1))) - p.weapon.aim_pitch_offset
    world.fire_shot(slot, yaw, pitch)
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
            p.buy_shield(2)                    # 重甲（有甲就不重複買）
        if p.weapon.stats.key == "classic" and p.economy.credits >= 3900:
            p.buy_weapon("vandal")             # 步槍 + 甲（2900+1000）
        return MoveInput()

    # --- 行動期 ---
    spike = world.spike
    is_attacker = p.team == TEAM_ATTACKERS
    enemy, dist = nearest_enemy(world, slot)
    st = spike.state.value if spike is not None else "idle"

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
            target = world.players[enemy].pos if enemy is not None else A_SITE   # 守點
        else:
            target = A_SITE                                                       # 衝點
    else:
        if st == "planted":
            target = spike._spike_pos()                                           # 回防拆彈
        elif enemy is not None and dist <= 20.0:
            target = world.players[enemy].pos                                     # 近敵才交戰
        else:
            target = DEFENDER_HOLDS[slot - 5]                                     # 否則卡點守備

    # 攻方執行安放：離 A 點 12m 內 → 無視交戰、直奔點位（真實攻點戰術）
    if is_attacker and st == "idle" and p.pos.distance_to(A_SITE) <= 12.0:
        d = A_SITE - p.pos
        d = Vec3(d.x, 0, d.z)
        if d.length() > 0.1:
            n = d.normalized()
            return MoveInput(forward=clamp(n.z, -1, 1), strafe=clamp(n.x, -1, 1))
        return MoveInput()

    # 移動向量
    d = target - p.pos
    d = Vec3(d.x, 0, d.z)
    if d.length() < 0.5:
        return MoveInput()
    n = d.normalized()
    move = MoveInput(forward=clamp(n.z, -1, 1), strafe=clamp(n.x, -1, 1))

    # 射擊：≤8m 視線清晰 → 急停開火；8–25m → 移動中壓制（避免無限僵局）
    if enemy is not None and dist <= 25.0:
        visible = try_shoot(world, slot, enemy)
        if visible and dist <= 8.0:
            return MoveInput()
        if not visible and dist <= 8.0:
            return move
    return move


def spike_demo() -> None:
    """腳本化 Spike 機制展示：安放 → 拆除（攻方勝 / 守方勝兩種結局）。"""
    print("=== Spike 機制展示 ===")
    print("場景 1：安放後無人拆除 → 45 秒爆炸，範圍致死")
    world = World(seed=7)
    world.start_match()
    spike = world.spike
    world.players[0].pos = Vec3(12, 0, 10)          # 安放手站進 A 點
    world.players[1].pos = Vec3(12, 0, 11)
    assert spike.try_begin_plant(0)
    for _ in range(int(4.2 / DT)):                  # 安放 4 秒
        world.step([None] * 10, DT)
    assert spike.state.value == "planted"
    print(f"  [t=4s] Spike 安放完成 @ {spike.site.name}（攻方全員 +300 經濟）")
    before = {i: world.players[i].health for i in range(5, 10)}
    for _ in range(int(46.0 / DT)):                 # 45 秒倒數
        world.step([None] * 10, DT)
    print(f"  [t=49s] 💥 Spike 爆炸！守方全滅：{before[5]:.0f}→{world.players[5].health:.0f}")

    print("\n場景 2：守方於 3.5s 檢查點後續拆 → 7 秒拆除成功")
    world = World(seed=7)
    world.start_match()
    spike = world.spike
    world.players[0].pos = Vec3(12, 0, 10)
    spike.try_begin_plant(0)
    for _ in range(int(4.2 / DT)):
        world.step([None] * 10, DT)
    world.players[5].pos = Vec3(12, 0, 10)          # 守方進入拆彈
    spike.try_begin_defuse(5)
    for _ in range(int(3.6 / DT)):                  # 拆到過半檢查點
        world.step([None] * 10, DT)
    spike.set_hold_defuse(5, False)                 # 中斷（去擊殺攻擊方）
    print(f"  [t=7.6s] 拆除過半 (3.5s 檢查點)，中斷後進度保留 "
          f"{spike.defuse_progress:.1f}s")
    spike.try_begin_defuse(5)                       # 回來續拆
    for _ in range(int(3.6 / DT)):
        world.step([None] * 10, DT)
    assert spike.state.value == "defused"
    print("  [t=11s] ✅ Spike 拆除成功，守方獲勝！\n")


def main():
    spike_demo()
    world = World(seed=2024)
    match = world.start_match()
    print("=== VANTA 全自動 AI 對戰示範 ===")
    print(f"地圖: 競技場 (A 點 @ {A_SITE.x},{A_SITE.z}) | 目標: 先拿 13 回合 | AI: 5v5\n")

    # Spike 事件紀錄旗標
    flags = {"plant": False, "defuse": False, "det": False}
    last_round = 1
    spike_events: list[str] = []

    t0 = time.perf_counter()
    for tick in range(MAX_TICKS):
        inputs = [bot_act(world, i) for i in range(10)]
        world.step(inputs, DT)

        s = world.spike
        if s is not None:
            st = s.state.value
            if st == "planted" and not flags["plant"]:
                spike_events.append(f"R{match.round}: Spike 安放完成 @ {s.site.name}")
                flags["plant"] = True
            elif st == "defused" and not flags["defuse"]:
                spike_events.append(f"R{match.round}: Spike 拆除成功！")
                flags["defuse"] = True
            elif st == "detonated" and not flags["det"]:
                spike_events.append(f"R{match.round}: 💥 Spike 爆炸！")
                flags["det"] = True
        if match.round != last_round:
            flags = {"plant": False, "defuse": False, "det": False}
            last_round = match.round
        if match.phase == RoundPhase.FINISHED:
            break
    elapsed = time.perf_counter() - t0

    sb = match.scoreboard()
    print("--- 回合紀錄 ---")
    for r in sb["records"]:
        winner = "攻方" if r["w"] == TEAM_ATTACKERS else "守方"
        print(f"  R{r['n']:>2}  勝方: {winner}  ({r['r']})")
    if spike_events:
        print("\n--- Spike 事件 ---")
        for e in spike_events:
            print("  " + e)
    print(f"\n最終比分: 攻方 {sb['scores'][TEAM_ATTACKERS]} - {sb['scores'][TEAM_DEFENDERS]} 守方")
    print(f"回合數: {match.round - 1} | 模擬 {tick * DT:.0f}s 遊戲時間")
    print(f"效能: 每 tick {(elapsed / (tick + 1)) * 1000:.2f} ms | 即時倍率 {tick * DT / elapsed:.1f}x")
    if match.phase == RoundPhase.FINISHED:
        winner = "攻方" if sb["scores"][TEAM_ATTACKERS] >= 13 else "守方"
        print(f"\n🏆 {winner} 獲得比賽勝利！")
    else:
        print("\n（時間到：比賽未打完）")

    print("\n--- 記分板 ---")
    print("槽位 隊  K/D  資金   武器      剩餘技能")
    for p in world.players:
        w = p.weapon.stats.name
        ab = "/".join(s.ability.name[:3] for s in p.abilities.slots if s.charges_left > 0) or "-"
        print(f"  {p.slot}   {'攻' if p.team == TEAM_ATTACKERS else '守'}  "
              f"{p.kills}/{p.deaths}  {p.economy.credits:>4}  {w:<9} {ab}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
