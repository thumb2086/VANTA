"""
tools/godot/serve.py — 本機權威伺服器（供 Godot 客戶端連線）
===========================================================
以真實 UDP 執行 128Hz 權威伺服器；可選 --ai 讓伺服器內建 AI 打整場比賽，
客戶端即可觀看/加入一場活躍對戰。

用法：
    python -m tools.godot.serve            # 空場伺服器（等真人連線）
    python -m tools.godot.serve --ai       # AI 對戰（客戶端可直接觀戰）
    python -m tools.godot.serve --port 7778
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from server.game.entities import World
from server.netcode.server_loop import GameServer
from server.netcode.timing import FixedTimestepLoop, SystemClock
from server.netcode.transport import UdpTransport

DT = 1.0 / 128.0

# AI 大腦：直接共用 Workers 版（分散卡點 / 反應延遲 / 連射節奏 / 會開槍），
# 避免兩份 AI 行為分歧（UDP 舊版：全員擠同一點、完全不開槍 → 「敵人疊在一起」）。
import os as _os
_WORKERS_SRC = _os.path.normpath(_os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "..", "workers", "src"))
sys.path.insert(0, _WORKERS_SRC)
from ai_bots import decide_bots as _decide_bots  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vanta-serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--ai", action="store_true", help="伺服器內建 AI 對戰")
    parser.add_argument("--seconds", type=float, default=0.0, help="0=無限")
    args = parser.parse_args(argv)

    world = World(seed=2024)
    match = world.start_match()
    transport = UdpTransport((args.host, args.port))
    server = GameServer(world=world, transport=transport, clock=SystemClock())
    if args.ai:
        # 快照必須包含無 Session 的 AI 槽位，否則客戶端看不到所有 bot
        server.broadcast_all_slots = True
    clock = SystemClock()

    def on_step(dt: float) -> None:
        # 重要：必須走 server.step()（收包/廣播/事件都在這裡）；
        # AI 輸入以 ai_inputs 注入「無 Session 槽位」，真人加入後自動取代。
        if args.ai:
            server.step(dt, ai_inputs=_decide_bots(world, match))
        else:
            server.step(dt)

    loop = FixedTimestepLoop(128, on_step, clock)
    print(f"⚔  VANTA 權威伺服器 @ {args.host}:{args.port}  ({'AI 對戰' if args.ai else '等待玩家'})")
    print(f"   執行 Godot 客戶端：Godot 開啟 client/project.godot 後按 F5")
    t0 = time.monotonic()
    try:
        while True:
            if args.seconds > 0 and time.monotonic() - t0 > args.seconds:
                break
            loop.advance()
            time.sleep(0.0005)      # 讓出 CPU（128Hz 每 tick 需 ~7.8ms）
    except KeyboardInterrupt:
        pass
    finally:
        transport.close()
    print(f"\n伺服器結束：tick={server.tick}, 事件={server.events_sent}, "
          f"比分={match.scores if match else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
