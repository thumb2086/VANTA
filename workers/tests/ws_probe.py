"""連線本機 wrangler dev（或部署後的 URL）驗證 WS 全流程。"""
import asyncio
import sys

sys.path.insert(0, "..")  # repo root (server 套件)
sys.path.insert(0, ".")

import websockets

from server.core.movement import MoveInput
from server.netcode.protocol import InputPacket, SnapshotPacket, WelcomePacket

URI = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8787/ws?match=test&ai=1"
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0


async def main():
    print(f"連線 {URI}")
    async with websockets.connect(URI) as ws:
        seq = 0

        async def pump():
            nonlocal seq
            while True:
                try:
                    await ws.send(InputPacket(net_id=0, input_seq=seq, client_time_ms=1,
                                              move=MoveInput(forward=1.0, strafe=0.0)).encode())
                    seq += 1
                except Exception:
                    return
                await asyncio.sleep(0.05)

        task = asyncio.create_task(pump())
        welcome = None
        n_snap = 0
        n_event = 0
        last_tick = -1
        max_tick = 0
        t0 = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - t0 < SECONDS:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                print("  (2s 無訊息)")
                continue
            if isinstance(msg, str):
                print("  TEXT:", msg[:100])
                continue
            data = bytes(msg)
            t = data[1]
            if t == 0x03:
                welcome = WelcomePacket.decode(data)
                print(f"  WELCOME net_id={welcome.net_id} slot={welcome.slot}")
            elif t == 0x02:
                n_snap += 1
                s = SnapshotPacket.decode(data)
                max_tick = max(max_tick, s.server_tick)
                if s.server_tick != last_tick and s.server_tick % 64 == 0:
                    last_tick = s.server_tick
                    e0 = s.state_for_slot(0)
                    e5 = s.state_for_slot(5)
                    alive = sum(1 for e in s.entries if e.occupied and e.health > 0)
                    print(f"  tick={s.server_tick} occupied={len(s.entries)} alive={alive} "
                          f"p0={e0.pos if e0 else '-'} hp={e0.health if e0 else '-'} "
                          f"p5={e5.pos if e5 else '-'}")
            elif t == 0x05:
                n_event += 1
                print(f"  EVENT id={data[2] | (data[3] << 8)}")
        task.cancel()
        print(f"\n結果: welcome={welcome} 快照={n_snap} 事件={n_event} max_tick={max_tick}")
        ok = welcome is not None and n_snap > 0 and max_tick >= 64
        print("PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)


asyncio.run(main())
