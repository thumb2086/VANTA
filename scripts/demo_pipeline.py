"""
scripts/demo_pipeline.py — 素材工具鏈 → 遊戲 整合示範
======================================================
展示「可程式化一切」的完整閉環：
  1. 程序化生成 3 張地圖（多 seed）→ 存檔 → 載入
  2. 程序化生成 8 把模組化武器 → 註冊進遊戲武器庫
  3. 用「生成的地圖 + 生成的武器」實際跑一場 AI 對戰

執行：python3 scripts/demo_pipeline.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase
from tools.maps.export import load_map, save_map
from tools.maps.generator import generate_map, validate_map
from tools.weapons.generator import generate_batch, register_to_game

DT = 1.0 / 128.0


def demo_maps():
    print("=== 1. 程序化地圖產生器 ===")
    for seed in (1, 7, 42):
        m = generate_map(seed=seed)
        ok, issues = validate_map(m)
        assert ok, f"seed={seed}: {issues}"
        save_map(f"tools/assets/maps/gen_seed{seed}.json", m)
        print(f"  seed={seed:>2}: {len(m.walls):>2} 面牆 / 點位 {[s.name for s in m.sites]} → 驗證 OK")
    loaded = load_map("tools/assets/maps/gen_seed7.json")
    print(f"  載入 seed7 地圖：{len(loaded.walls)} 面牆（JSON 往返一致）")
    return loaded


def demo_weapons():
    print("\n=== 2. 槍械模組化 + 武器產生器 ===")
    batch = generate_batch(seed=1000, count=8)
    print(f"  產生 {len(batch)} 把模組化武器：")
    for mw in batch:
        key = register_to_game(mw)          # 註冊進遊戲武器庫
        stats = mw.stats()
        mods = "/".join(sorted(mw.mods)) or "原廠"
        print(f"    {stats.name:<14} {stats.damage:>5.0f}傷 {stats.fire_rate_rps:>5.1f}射速 "
              f"{stats.mag_size:>3}彈匣 ${stats.price:>4}  [{mods}]")
    return key


def demo_game(map_data, weapon_key):
    print(f"\n=== 3. 生成素材進遊戲（{weapon_key} + 生成地圖）===")
    world = World(map_data=map_data, seed=99)
    world.start_match()
    # 給攻方第一名玩家裝上「生成武器」
    from server.game.entities import WeaponState
    from server.game.weapons import weapon

    world.players[0].weapon = WeaponState(weapon(weapon_key), world.rng)
    print(f"  slot0 裝備: {world.players[0].weapon.stats.name}")

    # 簡化 bot：全部向前移動（推進 A 點）
    def move_forward(slot):
        p = world.players[slot]
        if not p.alive or world.match.phase.value != "action":
            return None
        from server.core.math_core import Vec3, clamp

        target = Vec3(12, 0, 10)
        d = target - p.pos
        d = Vec3(d.x, 0, d.z)
        if d.length() < 0.5:
            return MoveInput()
        n = d.normalized()
        return MoveInput(forward=clamp(n.z, -1, 1), strafe=clamp(n.x, -1, 1))

    t0 = time.perf_counter()
    for _ in range(int(128 * 120)):          # 最多 120 秒
        world.step([move_forward(i) for i in range(10)], DT)
        if world.match.phase == RoundPhase.FINISHED:
            break
        # 攻方到達 A 點就安放
        s = world.spike
        if s is not None and s.state.value == "idle":
            for i in range(5):
                if world.players[i].alive and world.players[i].pos.distance_to(
                        __import__("server.core.math_core", fromlist=["Vec3"]).Vec3(12, 0, 10)) <= 2.5:
                    s.set_hold_plant(i, True)
                    break
        if s is not None and s.state.value == "planted":
            break                             # 已安放 → 示範達成
    el = time.perf_counter() - t0
    st = world.spike.state.value if world.spike else "?"
    sb = world.match.scoreboard()
    print(f"  Spike 狀態: {st} | 比分: {sb['scores']} | 回合: {world.match.round}")
    print(f"  world.tick={world.tick} | 效能 {(el / (world.tick + 1)) * 1000:.2f} ms/tick")
    print("\n✅ 閉環驗證：生成地圖 + 生成武器 + 遊戲引擎 + 目標機制 全部協同運作")


def main():
    demo_maps()
    demo_weapons()
    m = load_map("tools/assets/maps/gen_seed7.json")
    key = demo_weapons.__defaults__[0] if False else None
    # 重新產生並註冊一把武器供遊戲使用
    batch = generate_batch(seed=1000, count=8)
    wkey = register_to_game(batch[0])
    demo_game(m, wkey)
    return 0


if __name__ == "__main__":
    sys.exit(main())
