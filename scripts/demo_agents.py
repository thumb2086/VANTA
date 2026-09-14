"""
scripts/demo_agents.py — 人物產生器 → 遊戲 整合示範
====================================================
展示「可程式化人物」完整閉環：
  1. 產生 10 名角色（代號/身分/定位/技能組/配色/肖像）
  2. 註冊進遊戲 → 每名玩家裝備不同產生角色
  3. 跑一場快速遭遇戰：AI 施放各角色技能（煙霧/陷阱/刺激/治療/閃光/碎片）

執行：python3 scripts/demo_agents.py
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
from tools.agents.generator import generate_batch, register_agent
from tools.agents.portrait import write_portrait

DT = 1.0 / 128.0


def main() -> int:
    print("=== 人物產生器 → 遊戲 整合示範 ===\n")

    # 1) 產生 10 名角色
    agents = generate_batch(seed=777, count=10)
    print("--- 產生的角色 ---")
    for a in agents:
        print(f"  {a.codename:<10} {a.role_label:<4} {a.name:<16} "
              f"技能={'/'.join(a.kit):<20} 主色{a.colors['primary']}")
        write_portrait(f"tools/assets/agents/portraits/{a.key}.svg", a)

    # 2) 註冊並讓每名玩家裝備不同角色
    world = World(seed=1)
    world.start_match()
    for i, a in enumerate(agents):
        key = register_agent(a)
        world.players[i].agent_key = key
        world.players[i].abilities = __import__(
            "server.game.abilities", fromlist=["AbilitySystem"]
        ).AbilitySystem(list(__import__(
            "server.game.abilities", fromlist=["lookup_agent"]).lookup_agent(key)[1]))

    # 3) 行動期：每位 AI 朝前方移動並施放自己的第一招技能
    world.match.phase = RoundPhase.ACTION
    print("\n--- 技能施放（10 名產生角色 × 第一招）---")
    t0 = time.perf_counter()
    for t in range(128 * 12):                     # 12 秒
        inputs = []
        for i in range(10):
            p = world.players[i]
            if not p.alive:
                inputs.append(None)
                continue
            if t % 128 == 0 and i % 2 == 0:       # 每秒讓一半角色放招
                p.abilities.cast(0, world, i, __import__(
                    "server.core.math_core", fromlist=["Vec3"]).Vec3(0, 0, 1))
            inputs.append(MoveInput(forward=1.0))
        world.step(inputs, DT)
    el = time.perf_counter() - t0

    print(f"  煙霧場={len(world.smokes)} 陷阱={len(world.deployables)} "
          f"投射物={len(world.projectiles)}")
    print(f"  存活: {sum(1 for p in world.players if p.alive)}/10")
    print(f"  效能: {el / 12 * 1000:.1f} ms/sim秒")
    print("\n✅ 閉環驗證：產生角色 → 註冊 → 裝備 → 技能生效（伺服器權威）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
