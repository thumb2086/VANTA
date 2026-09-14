"""
workers/src/ws_transport.py — GameServer 傳輸介面的 WebSocket 適配
===================================================================
GameServer 依賴兩個方法：
  * recv_from() -> list[(addr, data)]   入站（WS 是 push 模式 → 回空，
    封包由 DO 直接呼叫 MatchHost.on_message → server.ingest）
  * send_to(data, addr)                 出站（快照/事件/welcome）

addr 即 ws_id（int）。真正把 bytes 送到瀏覽器/GD 客戶端的是
on_send 回呼（由 DO 接到 Workers WebSocket 的 ws.send）。
"""

from __future__ import annotations

from typing import Callable


class WSTransport:
    def __init__(self, on_send: Callable[[int, bytes], None] | None = None):
        self.on_send = on_send

    def recv_from(self) -> list:
        # 入站由 DO 主動推入（on_message → server.ingest），不經此處
        return []

    def send_to(self, data: bytes, addr: int) -> None:
        if self.on_send is not None:
            self.on_send(addr, data)
