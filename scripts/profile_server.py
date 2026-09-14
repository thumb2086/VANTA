"""
scripts/profile_server.py — 伺服器熱路徑效能剖析
================================================
以 cProfile 剖析 128Hz 權威伺服器（10 玩家 + AI 對戰 + 完整機制），
輸出：總成本、每 tick 成本、函式級熱點 TopN、即時倍率。

用法：python3 scripts/profile_server.py [模擬秒數]
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
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
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1.0 / 128.0


def build_ai_inputs(world):
    """輕量 AI：行動期朝 A 點推進並安放、守方卡點。"""
    from server.core.math_core import Vec3, clamp

    def act(slot):
        p = world.players[slot]
        if not p.alive:
            return None
        m = world.match
        if m is None or m.phase.value != "action":
            return MoveInput()
        A_SITE = Vec3(12, 0, 10)
        is_atk = p.team == 0
        spike = world.spike
        if spike is not None and spike.state.value == "idle" and is_atk and p.pos.distance_to(A_SITE) <= 2.5:
            spike.set_hold_plant(slot, True)
            return MoveInput()
        target = A_SITE if is_atk else Vec3(0, 0, 12)
        d = target - p.pos
        d = Vec3(d.x, 0, d.z)
        if d.length() < 0.5:
            return MoveInput()
        n = d.normalized()
        return MoveInput(forward=clamp(n.z, -1, 1), strafe=clamp(n.x, -1, 1))

    return {i: act(i) for i in range(10) if act(i) is not None}


def run_sim(seconds: float) -> tuple[int, float]:
    world = World(seed=2024)
    world.start_match()
    world.match.phase = RoundPhase.ACTION          # 直接進行動期（密集計算）
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=9)
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)

    # 模擬 2 個真實客戶端（收快照/送輸入）+ 8 個 AI 槽位
    from server.netcode.client_loop import GameClient
    clients = []
    for i in range(2):
        sim.set_link("server", f"c{i}", latency=0.04, loss_rate=0.01)
        clients.append(GameClient(transport=sim.create_endpoint(f"c{i}"),
                                  server_addr="server", clock=clock))

    t0 = time.perf_counter()
    ticks = int(seconds * 128)
    for t in range(ticks):
        for c in clients:
            c.poll()
            c.send_input(MoveInput(strafe=1.0, forward=0.5))
        clock.advance(DT)
        sim.flush()
        server.step(DT, ai_inputs=build_ai_inputs(world))
    return ticks, time.perf_counter() - t0


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    print(f"剖析 {seconds}s 遊戲時間 @ 128Hz（10 玩家：2 客戶端 + 8 AI，含網路模擬）...\n")

    pr = cProfile.Profile()
    pr.enable()
    ticks, wall = run_sim(seconds)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(18)
    print(s.getvalue())

    print("=" * 60)
    print(f"模擬 {seconds:.0f}s 遊戲時間 = {ticks} ticks")
    print(f"實際耗時 {wall:.2f}s → 即時倍率 {seconds / wall:.1f}x")
    print(f"每 tick 平均 {wall / ticks * 1000:.3f} ms")
    print(f"每 tick 每玩家 {wall / ticks / 10 * 1000:.4f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
