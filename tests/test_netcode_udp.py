"""Godot 客戶端 ↔ Python 權威伺服器：真實 UDP 整合測試。

驗證 Godot 客戶端使用的「線上協定」在真實 socket 上正確運作：
  welcome → 快照（含 health/mag）→ 遊戲事件（擊殺 / 回合勝負）。
"""

import socket
import threading
import time

import pytest

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase
from server.netcode.protocol import (
    EV_KILL,
    EV_ROUND_WIN,
    GameEventPacket,
    InputPacket,
    SnapshotPacket,
    WelcomePacket,
)
from server.netcode.server_loop import GameServer
from server.netcode.timing import SystemClock
from server.netcode.transport import UdpTransport


class FakeClient:
    """模仿 Godot NetClient 的 Python 假客戶端（使用同一協定）。"""

    def __init__(self, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self.server = ("127.0.0.1", port)
        self.net_id = -1
        self.slot = -1
        self.seq = 0
        self.snapshots = 0
        self.events = []

    def send_input(self, move: MoveInput) -> None:
        pkt = InputPacket(net_id=max(self.net_id, 0), input_seq=self.seq,
                          client_time_ms=int(time.time() * 1000) & 0xFFFFFFFF, move=move)
        self.sock.sendto(pkt.encode(), self.server)
        self.seq += 1

    def poll(self, timeout: float = 0.5) -> None:
        """收一次包。"""
        self.sock.settimeout(timeout)
        try:
            data, _ = self.sock.recvfrom(1024)
        except socket.timeout:
            return
        if len(data) < 2 or data[0] != 0x56:
            return
        if data[1] == 0x03:      # welcome
            w = WelcomePacket.decode(data)
            if w is not None:
                self.net_id, self.slot = w.net_id, w.slot
        elif data[1] == 0x02:    # snapshot
            s = SnapshotPacket.decode(data)
            if s is not None:
                self.snapshots += 1
                self.last_snapshot = s
        elif data[1] == 0x05:    # game event
            e = GameEventPacket.decode(data)
            if e is not None:
                self.events.append(e)


@pytest.fixture()
def server_thread():
    """在背景執行緒跑 128Hz 權威伺服器（真實 UDP）。"""
    world = World(seed=3)
    world.start_match()
    tr = UdpTransport(("127.0.0.1", 0))
    server = GameServer(world=world, transport=tr, clock=SystemClock())
    port = tr.addr[1]
    stop = threading.Event()

    def run():
        loop = None
        from server.netcode.timing import FixedTimestepLoop

        loop = FixedTimestepLoop(128, lambda dt: server.step(dt), SystemClock())
        while not stop.is_set():
            loop.advance()
            time.sleep(0.001)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    yield world, server, port
    stop.set()
    th.join(timeout=2.0)


def test_welcome_and_snapshot_flow(server_thread):
    world, server, port = server_thread
    c = FakeClient(port)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        c.send_input(MoveInput(forward=1.0))
        c.poll(0.3)
        if c.snapshots > 0:
            break
    assert c.net_id >= 0, "未收到 welcome"
    assert c.slot >= 0
    assert c.snapshots > 0, "未收到快照"
    assert c.last_snapshot.server_tick > 0
    # 快照內含自己的血量/彈匣
    me = c.last_snapshot.state_for_slot(c.slot)
    assert me is not None and me.occupied
    assert me.health == 100
    assert me.mag >= 0
    # 伺服器世界正常推進（tick 持續成長）
    t1 = server.tick
    time.sleep(0.5)
    assert server.tick > t1


def test_game_events_broadcast(server_thread):
    world, server, port = server_thread
    c = FakeClient(port)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        c.send_input(MoveInput())
        c.poll(0.3)
        if c.snapshots > 0:
            break
    # 讓回合進入行動期並全滅守方 → 觸發擊殺 + 回合勝利事件
    world.match.phase = RoundPhase.ACTION
    for i in range(5, 10):
        world.players[i].apply_damage(9999, source_slot=0, weapon_key="test")
    deadline = time.time() + 5.0
    got_events = set()
    while time.time() < deadline:
        c.poll(0.3)
        got_events.update(e.event for e in c.events)
        if EV_ROUND_WIN in got_events:
            break
    assert EV_KILL in got_events, f"未收到擊殺事件: {got_events}"
    assert EV_ROUND_WIN in got_events, f"未收到回合勝利事件: {got_events}"
    # 事件帶正確參數（擊殺兇手/受害者槽位）
    kills = [e for e in c.events if e.event == EV_KILL]
    assert len(kills) >= 5
    assert all(e.p0 == 0 for e in kills)           # 兇手 = slot0
    assert {e.p1 for e in kills} == {5, 6, 7, 8, 9} # 受害者 = 全部守方


def test_input_moves_player(server_thread):
    world, server, port = server_thread
    c = FakeClient(port)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        c.send_input(MoveInput(strafe=1.0))   # 向東（出生點 (-14,-16)，前方是重生大樓牆）
        c.poll(0.3)
        if c.snapshots > 3:
            break
    # 買期移動凍結（正確機制）→ 切到行動期後輸入才會生效
    world.match.phase = RoundPhase.ACTION
    deadline = time.time() + 5.0
    while time.time() < deadline:
        c.send_input(MoveInput(strafe=1.0))
        c.poll(0.3)
        if server.world.players[c.slot].pos.x > -11.0:
            break
    # 假客戶端持續按 D → 伺服器上的玩家應向東移動（出生點 (-14,-16)）
    assert server.world.players[c.slot].pos.x > -11.0
