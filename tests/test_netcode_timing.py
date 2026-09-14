"""M2 固定時間步迴圈與虛擬時鐘測試。"""

import pytest

from server.netcode.timing import FixedTimestepLoop, VirtualClock


def test_virtual_clock_advance():
    c = VirtualClock()
    assert c.now() == 0.0
    c.advance(0.5)
    assert c.now() == 0.5


def test_exact_128_steps_per_second():
    """1/128 是 2 的冪 → 無浮點累積誤差，1 虛擬秒恰執行 128 步。"""
    clock = VirtualClock()
    steps, dts = [], []
    loop = FixedTimestepLoop(
        rate_hz=128, on_step=lambda dt: dts.append(dt), clock=clock, max_steps_per_frame=256
    )
    clock.advance(1.0)
    n = loop.advance()
    assert n == 128
    assert loop.steps_run == 128
    assert all(d == pytest.approx(1 / 128) for d in dts)


def test_one_step_per_tick_aligned():
    """每幀恰好推進一個 dt → 每幀 1 步。"""
    clock = VirtualClock()
    n_steps = 0
    loop = FixedTimestepLoop(128, lambda dt: n_steps + 1, clock=clock)  # 不使用參數亦可
    # 改用計數器
    counts = []
    loop2 = FixedTimestepLoop(128, lambda dt: counts.append(dt), clock=clock)
    for _ in range(64):
        clock.advance(1 / 128)
        loop2.advance()
    assert len(counts) == 64
    assert loop2.steps_run == 64


def test_max_steps_per_frame_clamp():
    """一次推進 10 秒 → 最多執行 max_steps_per_frame 步（防死亡螺旋）。"""
    clock = VirtualClock()
    n = [0]
    loop = FixedTimestepLoop(128, lambda dt: n.__setitem__(0, n[0] + 1), clock=clock, max_steps_per_frame=16)
    clock.advance(10.0)
    ran = loop.advance()
    assert ran == 16
    assert n[0] == 16


def test_partial_frame_accumulates():
    """推進小於一個 dt → 0 步，但時間累積，之後補足。"""
    clock = VirtualClock()
    counts = []
    loop = FixedTimestepLoop(128, lambda dt: counts.append(dt), clock=clock)
    clock.advance(1 / 256)          # 半個 tick
    assert loop.advance() == 0
    clock.advance(1 / 256)          # 補足一個 tick
    assert loop.advance() == 1
    assert len(counts) == 1
