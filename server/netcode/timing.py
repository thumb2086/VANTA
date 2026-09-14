"""
server/netcode/timing.py — 固定時間步迴圈與時鐘抽象
=====================================================
伺服器核心迴圈使用「固定時間步 + 累加器 (accumulator)」：
  * 模擬只接受固定 dt（128Hz → 1/128 = 0.0078125s，2 的冪 → float 精確表示）
  * 時間來源注入（VirtualClock 供測試 / SystemClock 供生產）
  * max_steps_per_frame 防止「死亡螺旋」（一幀內無限補步）
"""

from __future__ import annotations

from typing import Callable, Protocol


class Clock(Protocol):
    """時鐘介面：模擬/伺服器所需的唯一時間來源。"""

    def now(self) -> float: ...


class VirtualClock:
    """測試用虛擬時鐘：完全由測試推進，保證確定性。"""

    def __init__(self, t0: float = 0.0):
        self._t = t0

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt


class SystemClock:
    """生產用系統時鐘（單調遞增，不受系統時間回撥影響）。"""

    import time as _time  # 延遲 import 以保持模組輕量

    def now(self) -> float:
        return self._time.monotonic()


class FixedTimestepLoop:
    """固定時間步主迴圈。

    用法：
        loop = FixedTimestepLoop(rate_hz=128, on_step=server.step, clock=clock)
        while running:
            loop.advance()          # 每「幀」呼叫一次
    """

    def __init__(
        self,
        rate_hz: int,
        on_step: Callable[[float], None],
        clock: Clock,
        max_steps_per_frame: int = 16,
    ):
        self.dt = 1.0 / rate_hz
        self.rate_hz = rate_hz
        self._on_step = on_step
        self._clock = clock
        self.max_steps_per_frame = max_steps_per_frame
        self.accumulator = 0.0
        self.last_time = clock.now()
        self.steps_run = 0

    def advance(self) -> int:
        """讀取時鐘、執行 0..max_steps 個固定步。回傳本次執行的步數。"""
        now = self._clock.now()
        self.accumulator += now - self.last_time
        self.last_time = now

        n = 0
        while self.accumulator >= self.dt and n < self.max_steps_per_frame:
            self._on_step(self.dt)          # 模擬永遠收到固定 dt
            self.accumulator -= self.dt
            n += 1
        self.steps_run += n
        return n
