"""
server/netcode/transport.py — 傳輸抽象
======================================
設計原則：伺服器/客戶端邏輯只依賴極簡的「類 UDP」介面，因此：

  * InMemoryEndpoint + NetworkSimulator：純記憶體、可注入延遲/遺失/抖動、
    種子化（確定性）→ 所有網路測試不需要真實 socket。
  * UdpTransport：生產用 stdlib 非阻塞 UDP。

介面（兩個實作一致）：
    send_to(data: bytes, dest) -> None
    recv_from() -> list[(src, data)]
"""

from __future__ import annotations

import random
import socket
from dataclasses import dataclass

from server.netcode.timing import Clock, VirtualClock


# ---------------------------------------------------------------------- #
# 記憶體網路（測試）
# ---------------------------------------------------------------------- #
@dataclass(slots=True)
class LinkParams:
    """鏈路參數：單向延遲 / 遺失率 / 抖動（uniform 0..jitter）。"""

    latency: float = 0.0
    loss_rate: float = 0.0
    jitter: float = 0.0


@dataclass(slots=True)
class _PendingPacket:
    deliver_at: float
    src: str
    dest: str
    data: bytes


class InMemoryEndpoint:
    """單一端點（伺服器或客戶端）的類 UDP 介面。"""

    def __init__(self, sim: "NetworkSimulator", eid: str):
        self.sim = sim
        self.eid = eid
        self._inbox: list[tuple[str, bytes]] = []

    # -- 類 UDP 介面 --
    def send_to(self, data: bytes, dest: str) -> None:
        self.sim._route(self.eid, dest, data)

    def recv_from(self) -> list[tuple[str, bytes]]:
        out, self._inbox = self._inbox, []
        return out

    # -- 內部（由 NetworkSimulator 呼叫）--
    def _deliver(self, src: str, data: bytes) -> None:
        self._inbox.append((src, data))


class NetworkSimulator:
    """一個「網路」：管理多個端點與端點間鏈路，模擬延遲/遺失/抖動。

    確定性：所有隨機取樣（遺失、抖動）都來自注入種子的 rng，
    呼叫順序固定 → 相同種子 + 相同腳本 = 完全相同行為。
    """

    def __init__(self, clock: Clock | None = None, seed: int = 42):
        self.clock = clock if clock is not None else VirtualClock()
        self.rng = random.Random(seed)
        self.endpoints: dict[str, InMemoryEndpoint] = {}
        self.links: dict[tuple[str, str], LinkParams] = {}
        self._pending: list[_PendingPacket] = []

    def create_endpoint(self, eid: str) -> InMemoryEndpoint:
        ep = InMemoryEndpoint(self, eid)
        self.endpoints[eid] = ep
        return ep

    def set_link(self, a: str, b: str, latency=0.0, loss_rate=0.0, jitter=0.0) -> None:
        self.links[(a, b)] = LinkParams(latency, loss_rate, jitter)
        self.links[(b, a)] = LinkParams(latency, loss_rate, jitter)

    def flush(self) -> None:
        """將所有已到期封包交付（每次模擬 tick 呼叫一次）。"""
        now = self.clock.now()
        due = [p for p in self._pending if p.deliver_at <= now]
        self._pending = [p for p in self._pending if p.deliver_at > now]
        # 依 deliver_at 排序 → 同時到期的封包以「入網順序」交付（確定性）
        due.sort(key=lambda p: p.deliver_at)
        for p in due:
            dst = self.endpoints.get(p.dest)
            if dst is not None:
                dst._deliver(p.src, p.data)

    # -- 內部 --
    def _route(self, src: str, dest: str, data: bytes) -> None:
        link = self.links.get((src, dest), LinkParams())
        if self.rng.random() < link.loss_rate:
            return                       # 封包遺失
        delay = link.latency
        if link.jitter > 0.0:
            delay += self.rng.uniform(0.0, link.jitter)
        self._pending.append(
            _PendingPacket(deliver_at=self.clock.now() + delay, src=src, dest=dest, data=data)
        )
        # 依 deliver_at 排序插入以保持確定交付順序
        self._pending.sort(key=lambda p: p.deliver_at)


# ---------------------------------------------------------------------- #
# 生產 UDP（真實 socket）
# ---------------------------------------------------------------------- #
class UdpTransport:
    """非阻塞 UDP 傳輸。介面與 InMemoryEndpoint 一致（src = 位址 tuple）。"""

    def __init__(self, bind_addr=("0.0.0.0", 0)):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(bind_addr)
        self.sock.setblocking(False)
        self.addr = self.sock.getsockname()

    def send_to(self, data: bytes, dest) -> None:
        self.sock.sendto(data, dest)

    def recv_from(self) -> list[tuple[tuple, bytes]]:
        out: list[tuple[tuple, bytes]] = []
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
                out.append((addr, data))
            except BlockingIOError:
                break
            except InterruptedError:
                continue
            except ConnectionResetError:
                # Windows：對端關閉 socket 時，下一個 recvfrom 會收到
                # ICMP port unreachable → WinError 10054；UDP 語義上應忽略。
                continue
        return out

    def close(self) -> None:
        self.sock.close()
