"""
rust/parity/golden_protocol.py — 二進位封包 SerDe 黃金資料
==========================================================
以 Python 協定實作產生各種封包（INPUT / SNAPSHOT / WELCOME / GAME_EVENT），
寫成 packets.bin（[len u32][bytes]）。Rust 端必須 decode → re-encode 出相同位元組
（證明 Rust 的欄位偏移與 Python struct 布局完全一致）。
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.netcode.protocol import (
    EV_KILL,
    GameEventPacket,
    InputPacket,
    SnapshotEntry,
    SnapshotPacket,
    WelcomePacket,
)

OUT = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    packets: list[bytes] = []

    # INPUT：典型 + 極端值（負數、clamp 邊界、全旗標）
    packets.append(InputPacket(net_id=7, input_seq=12345, client_time_ms=67890,
                               move=MoveInput(forward=0.5, strafe=-1.0, walk=True, jump=True)).encode())
    packets.append(InputPacket(net_id=65535, input_seq=4294967295, client_time_ms=0,
                               move=MoveInput(forward=-2.0, strafe=2.0, crouch=True)).encode())

    # SNAPSHOT：多槽位佔用 + 空槽位 + 極端值
    entries = [
        SnapshotEntry(slot=0, pos=Vec3(12.34, 0.0, -7.89), vel=Vec3(5.43, -2.1, 0.0),
                      on_ground=True, crouching=False, walking=True, occupied=True,
                      echo_client_time_ms=999, last_input_seq=77, health=87, mag=12,
                      reloading=True, weapon_slot=0, reload_progress=127),
        SnapshotEntry(slot=3, pos=Vec3(-327.67, 1.5, 327.67), vel=Vec3(0.01, -0.02, 0.03),
                      on_ground=False, crouching=True, walking=False, occupied=True,
                      echo_client_time_ms=42, last_input_seq=4294967295, health=255, mag=0,
                      reloading=False, weapon_slot=2, reload_progress=255),
        SnapshotEntry(slot=9, pos=Vec3(0.005, 0.0, -0.005), vel=Vec3(),
                      on_ground=True, crouching=False, walking=False, occupied=True,
                      echo_client_time_ms=1, last_input_seq=-1, health=0, mag=30,
                      reloading=True, weapon_slot=1, reload_progress=3),
    ]
    packets.append(SnapshotPacket(server_tick=2048, entries=entries).encode())
    # 全空快照
    packets.append(SnapshotPacket(server_tick=0, entries=[]).encode())

    # WELCOME
    packets.append(WelcomePacket(net_id=5, slot=3).encode())

    # GAME_EVENT
    packets.append(GameEventPacket(event=EV_KILL, server_tick=1234, p0=3, p1=7).encode())

    # MATCH_STATE
    from server.netcode.protocol import MatchStatePacket
    packets.append(MatchStatePacket(
        server_tick=2048, phase=1, round=3, round_timer_ms=45123,
        spike_state=2, spike_fuse_s=40, score_a=2, score_b=1, attacker_team=0,
        credits=tuple([4300] * 5 + [2700] * 5)).encode())

    with open(os.path.join(OUT, "packets.bin"), "wb") as f:
        for p in packets:
            f.write(struct.pack("<I", len(p)))
            f.write(p)
    print(f"協定黃金資料完成: {len(packets)} 個封包（INPUT/SNAPSHOT/WELCOME/GAME_EVENT）")


if __name__ == "__main__":
    main()
