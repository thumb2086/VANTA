"""
rust/parity/golden_recoil.py — 後座力 + 種子化 RNG 黃金資料
===========================================================
以「專屬 RNG 實例」驅動 RecoilController（Vandal 圖案），
輸出：schedule.bin（每 tick 是否開火）＋ states_recoil.bin（pitch/yaw/索引）。

時間軸涵蓋：爆發 10 發（保護彈 6 + 隨機 4）→ 完全恢復 → 短爆發 →
部分恢復 → 再爆發（未恢復時累積）。Rust 端必須重放出一模一樣的序列。
"""

from __future__ import annotations

import os
import random
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server.core.rng import MT19937
from server.game.recoil import PATTERNS, RecoilController

DT = 1.0 / 128.0
T = 2000
OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 42


def build_schedule() -> list[bool]:
    fire = [False] * T
    # 爆發 1：10 發（tick 0..9）→ 覆蓋保護彈 6 + 隨機 4
    for t in range(10):
        fire[t] = True
    # 爆發 2：4 發（tick 300..303）
    for t in range(300, 304):
        fire[t] = True
    # 爆發 3：5 發（tick 340..344）— 前次只過了 40 ticks(0.31s) < reset 0.7s → 未恢復
    for t in range(340, 345):
        fire[t] = True
    return fire


def main() -> None:
    rng = MT19937(SEED)                    # 確定性 RNG（與 Rust 端位元級一致）
    ctrl = RecoilController(PATTERNS["vandal"], rng)
    fire = build_schedule()

    with open(os.path.join(OUT, "schedule_recoil.bin"), "wb") as fsched, \
         open(os.path.join(OUT, "states_recoil.bin"), "wb") as fstate:
        fsched.write(struct.pack("<I", T))
        fsched.write(bytes(1 if f else 0 for f in fire))
        for t in range(T):
            now = t * DT
            if fire[t]:
                ctrl.fire(now)
            ctrl.update(now, DT)
            fstate.write(struct.pack("<ddII", ctrl.pitch, ctrl.yaw,
                                     ctrl.bullet_index, ctrl.shots_fired))
    print(f"後座力黃金資料完成: {T} ticks（seed={SEED}, 圖案=vandal）")


if __name__ == "__main__":
    main()
