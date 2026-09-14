"""
workers/src/match_host.py — VANTA match host（Workers-agnostic）
================================================================
把 UDP 權威伺服器（server/netcode/server_loop.GameServer）改造成
「WebSocket + 事件驅動」的比賽主機：

  * 連線抽象：addr = 整數 ws_id；傳輸介面由 WSTransport 對接
  * 事件驅動 tick：每收到訊息 / alarm 喚醒時，依牆鐘時間補跑固定步
    （1/128s），與原 UDP 版「固定時間步 + 累加器」語義一致 → 確定性不變
  * 反作弊 / Rollback / 去重 / 快照廣播：完全沿用 GameServer，零改動

此模組不 import 任何 Workers API，可在本機用 pytest 直接驗證；
DO 端（entry.py 的 MatchDO）只負責把 Workers WebSocket 事件轉成
這些方法呼叫。
"""

from __future__ import annotations

import time
from typing import Callable

from server.game.entities import World
from server.netcode.server_loop import GameServer
from server.netcode.timing import SystemClock

from ai_bots import decide_bots
from ws_transport import WSTransport

RATE_HZ = 128
DT = 1.0 / RATE_HZ
# 單次喚醒最多補跑的 tick（避免積壓→死亡螺旋；超出的時間直接丟棄）
MAX_TICKS_PER_WAKE = 512


class MatchHost:
    """一場比賽的主機。對外方法：connect / on_message / on_close / advance。

    :param seed:        確定性種子（同一 seed → 同一場比賽）
    :param ai_mode:     True 時空槽位由內建 AI 補位（觀戰/示範模式）
    :param on_send:     callable(ws_id: int, data: bytes)，把伺服器出站資料
                        （welcome / 每 tick 快照 / 事件）送給對應連線
    :param now_fn:      時鐘（測試注入），預設 time.monotonic
    """

    def __init__(
        self,
        seed: int = 42,
        ai_mode: bool = False,
        mode: str = "competitive",
        on_send: Callable[[int, bytes], None] | None = None,
        now_fn: Callable[[], float] | None = None,
    ):
        self.seed = seed
        self.ai_mode = ai_mode
        self.mode = mode
        self.on_send = on_send
        self._now = now_fn or time.monotonic

        self.world = World(seed=seed)
        self.world.start_match(mode=mode)
        self.transport = WSTransport(on_send=self.on_send)
        self.server = GameServer(self.world, transport=self.transport,
                                 clock=SystemClock(), rate_hz=RATE_HZ)
        self.server.broadcast_all_slots = ai_mode     # AI 觀戰：所有 10 名玩家可見

        self._last = self._now()
        self._accum = 0.0
        self.steps_run = 0
        self._next_ws_id = 1

    # ------------------------------------------------------------------ #
    # 連線生命週期（addr = ws_id；session 在「第一個封包」才建立，
    # 與 UDP 版一致——welcome 於 session 建立時送出）
    # ------------------------------------------------------------------ #
    def connect(self) -> int:
        ws_id = self._next_ws_id
        self._next_ws_id += 1
        return ws_id

    def on_message(self, ws_id: int, data: bytes) -> int:
        """收到客戶端封包：ingest 進 GameServer，然後補跑 tick。"""
        self.server.ingest(ws_id, data)
        return self.advance()

    def on_close(self, ws_id: int) -> None:
        """連線關閉：釋放 session（槽位），與 UDP 斷線逾時同路徑。"""
        sess = self.server.sessions.pop(ws_id, None)
        if sess is not None:
            self.server._slot_addrs.pop(sess.slot, None)
            self.server.free_slots.append(sess.slot)
            self.server.free_slots.sort()
            if self.server.on_player_left is not None:
                self.server.on_player_left(sess)

    def session_count(self) -> int:
        return len(self.server.sessions)

    # ------------------------------------------------------------------ #
    # 事件驅動 tick（固定步長 + 累加器，與 FixedTimestepLoop 同語義）
    # ------------------------------------------------------------------ #
    def advance(self, now: float | None = None, max_ticks: int = MAX_TICKS_PER_WAKE) -> int:
        t = now if now is not None else self._now()
        dt = t - self._last
        self._last = t
        if dt <= 0:
            return 0
        self._accum += dt
        n = 0
        while self._accum >= DT and n < max_ticks:
            ai = self._ai_inputs() if self.ai_mode else None
            self.server.step(ai_inputs=ai)
            self._accum -= DT
            n += 1
        if n == max_ticks:
            # 積壓超過上限 → 丟棄剩餘時間，避免死亡螺旋
            self._accum = 0.0
        self.steps_run += n
        return n

    def _ai_inputs(self) -> dict[int, object] | None:
        """空槽位的 AI 輸入（真人 session 優先——GameServer.step 只補沒人的槽）。

        節流決策（decide_bots 每 4 tick 重新決策）→ 伺服器維持即時 128Hz。
        """
        occupied = {sess.slot for sess in self.server.sessions.values()}
        decided = decide_bots(self.world, None)
        return {slot: m for slot, m in decided.items() if slot not in occupied}
        return out if out else None
