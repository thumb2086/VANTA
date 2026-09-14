"""
rust/parity/golden.py — 產生黃金軌跡資料（供 Rust 端比對）
==========================================================
以固定輸入腳本驅動 Python MovementController，輸出：
  * inputs.bin   每 tick 輸入（f64 forward, f64 strafe, u8 flags: walk|crouch|jump）
  * states.bin   每 tick 位置/速度（f64 LE × 6）——Rust 端必須位元組級一致

用法：python3 rust/parity/golden.py
"""

from __future__ import annotations

import os
import random
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server.core.movement import MovementConfig, MovementController, MoveInput

DT = 1.0 / 128.0
TICKS = 2000
OUT = os.path.dirname(os.path.abspath(__file__))


def make_inputs() -> list[MoveInput]:
    """固定腳本：跑→反切→靜步→跳→蹲→斜向（覆蓋所有分支）。"""
    rng = random.Random(2024)
    inputs = []
    phase = 0
    for t in range(TICKS):
        if t < 300:
            inp = MoveInput(forward=1.0)                 # 直跑
        elif t < 500:
            inp = MoveInput(strafe=1.0)                  # 右橫移
        elif t < 560:
            inp = MoveInput(strafe=-1.0)                 # 反切急停
        elif t < 700:
            inp = MoveInput(forward=1.0, walk=True)      # 靜步
        elif t < 720:
            inp = MoveInput(jump=True)                   # 跳躍
        elif t < 900:
            inp = MoveInput(forward=1.0, crouch=True)    # 蹲走
        elif t < 1100:
            inp = MoveInput(strafe=1.0, forward=1.0)     # 斜向
        elif t < 1300:
            inp = MoveInput(forward=1.0, jump=True)      # 跳躍緩衝
        elif t < 1500:
            inp = MoveInput(strafe=-1.0, walk=True)
        else:
            # 隨機（種子化）——確定性腳本
            inp = MoveInput(
                forward=rng.uniform(-1, 1),
                strafe=rng.uniform(-1, 1),
                walk=rng.random() < 0.2,
                crouch=rng.random() < 0.1,
                jump=rng.random() < 0.02,
                ads=rng.random() < 0.15,
            )
        inputs.append(inp)
    return inputs


def main() -> None:
    ctrl = MovementController(MovementConfig(), ground_y=0.0)
    inputs = make_inputs()

    with open(os.path.join(OUT, "inputs.bin"), "wb") as fi, \
         open(os.path.join(OUT, "states.bin"), "wb") as fs:
        for inp in inputs:
            fi.write(struct.pack("<ddB", inp.forward, inp.strafe,
                                 (1 if inp.walk else 0) | (2 if inp.crouch else 0)
                                 | (4 if inp.jump else 0) | (8 if getattr(inp, "ads", False) else 0)))
        for inp in inputs:
            ctrl.step(inp, DT)
            fs.write(struct.pack("<dddddd", ctrl.pos.x, ctrl.pos.y, ctrl.pos.z,
                                 ctrl.vel.x, ctrl.vel.y, ctrl.vel.z))
    print(f"黃金資料完成: {len(inputs)} ticks → {os.path.join(OUT, 'inputs.bin')} / states.bin")


if __name__ == "__main__":
    main()
