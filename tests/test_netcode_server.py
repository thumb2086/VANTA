"""
M2 伺服器主迴圈整合測試。

覆蓋：
  1. 客戶端加入（歡迎封包、槽位分配）
  2. 多玩家同時遊玩 → 世界狀態推進、快照遞增
  3. 確定性：相同種子 + 相同腳本 → 位元級相同世界狀態
  4. 去重：同一 seq 輸入重送只處理一次
  5. 斷線逾時：逾時後釋放槽位、新客戶端可重用
  6. 無損回放：錄製 ingest_log → 重放 → 逐 tick 世界狀態一致（驗收標準）
"""

import math

from server.core.movement import MoveInput
from server.game.world import World
from server.netcode.client_loop import GameClient
from server.netcode.protocol import WelcomePacket
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1.0 / 128.0


def build_harness(latency=0.05, loss=0.0, seed=42, n_clients=2):
    """建立 虛擬時鐘 + 網路 + 伺服器 + n 個客戶端。"""
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=seed)
    server_ep = sim.create_endpoint("server")
    world = World()
    server = GameServer(world=world, transport=server_ep, clock=clock)
    sim.set_link("server", "c0", latency=latency, loss_rate=loss)
    sim.set_link("server", "c1", latency=latency, loss_rate=loss)
    clients = []
    for i in range(n_clients):
        ep = sim.create_endpoint(f"c{i}")
        cl = GameClient(transport=ep, server_addr="server", clock=clock)
        clients.append(cl)
    return clock, sim, server, clients


def run_script(clock, sim, server, clients, script, ticks):
    """
    驅動一局：每個 tick 依 script[tick] 餵入輸入（MoveInput | None = 不送）。
    回傳每 tick 的伺服器世界位置快照（供確定性/回放比對）。
    """
    states_log = []
    for t in range(ticks):
        for ci, cl in enumerate(clients):
            cl.poll()
            inp = script[t][ci] if t < len(script) else None
            if inp is not None:
                cl.send_input(inp)
        clock.advance(DT)
        sim.flush()
        server.step(DT)
        states_log.append(tuple((p.slot, p.pos.x, p.pos.y, p.pos.z) for p in server.world.states()))
    return states_log


def moving_script(ticks, n_clients=2):
    """簡單的移動腳本：c0 向右、c1 向前（都是可重現的固定模式）。"""
    script = []
    for t in range(ticks):
        c0 = MoveInput(strafe=1.0)
        c1 = MoveInput(forward=1.0)
        script.append([c0, c1])
    return script


# --------------------------------------------------------------------- #
# 1. 加入與快照
# --------------------------------------------------------------------- #
def test_join_welcome_and_slots():
    clock, sim, server, clients = build_harness(n_clients=2)
    script = moving_script(64)
    run_script(clock, sim, server, clients, script, 64)

    assert len(server.sessions) == 2
    slots = sorted(s.slot for s in server.sessions.values())
    assert slots == [0, 1]
    # 客戶端收到歡迎封包並知道自己的 net_id/slot
    for cl in clients:
        assert cl.net_id is not None
        assert cl.slot is not None
        assert cl.snapshot_count > 0


def test_world_advances_and_snapshots_increase():
    clock, sim, server, clients = build_harness(latency=0.02, n_clients=2)
    script = moving_script(256)
    run_script(clock, sim, server, clients, script, 256)

    # 兩個玩家都移動了（c0 由 (-14,-16) 滿速向右 10.5m、c1 由 (-7,-16) 向前被大樓牆擋停）
    assert server.world.players[0].pos.x > -4.0
    assert server.world.players[1].pos.z > -15.0     # 從 -16 前進至少 1m
    # 客戶端最後收到的 server_tick 嚴格遞增且接近 256
    for cl in clients:
        assert cl.last_server_tick > 200
        assert cl.snapshot_count > 0


# --------------------------------------------------------------------- #
# 2. 確定性
# --------------------------------------------------------------------- #
def test_determinism_bit_exact():
    def run_once():
        clock, sim, server, clients = build_harness(latency=0.03, seed=99)
        return run_script(clock, sim, server, clients, moving_script(512), 512)

    a = run_once()
    b = run_once()
    assert a == b                      # 逐 tick 位元級相同
    assert len(a) == 512


# --------------------------------------------------------------------- #
# 3. 去重（重送防護）
# --------------------------------------------------------------------- #
def test_duplicate_input_ignored():
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=1)
    server_ep = sim.create_endpoint("server")
    server = GameServer(world=World(), transport=server_ep, clock=clock)
    ep = sim.create_endpoint("c")
    cl = GameClient(transport=ep, server_addr="server", clock=clock)

    # 直接注入兩份相同 seq 的封包（模擬 UDP 重送）
    import struct
    from server.netcode.protocol import InputPacket, MAGIC, TYPE_INPUT, INPUT_PACKET_SIZE, FLAG_JUMP

    def raw_input(seq):
        pkt = InputPacket(net_id=1, input_seq=seq, client_time_ms=100, move=MoveInput(forward=0.0, jump=True))
        return pkt.encode()

    server.ingest("c", raw_input(0))
    server.ingest("c", raw_input(0))    # 重送 → 應被 seen 去重

    server.step(DT)                      # tick1：處理 seq0（跳躍）
    assert server.world.players[0].vel.y > 0.0
    vy_after = server.world.players[0].vel.y

    server.step(DT)                      # tick2：若重送未被去重，會再跳一次（vy 又重置為 4.6）
    assert server.world.players[0].vel.y < vy_after      # 正常重力作用下 v 下降 → 證明只跳一次

    sess = next(iter(server.sessions.values()))
    assert sess.last_processed_seq == 0


# --------------------------------------------------------------------- #
# 4. 斷線逾時與槽位重用
# --------------------------------------------------------------------- #
def test_disconnect_timeout_frees_slot():
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=1)
    server_ep = sim.create_endpoint("server")
    server = GameServer(world=World(), transport=server_ep, clock=clock, timeout_s=2.0)

    ep = sim.create_endpoint("c")
    cl = GameClient(transport=ep, server_addr="server", clock=clock)
    cl.send_input(MoveInput())
    clock.advance(DT)
    sim.flush()
    server.step(DT)
    assert len(server.sessions) == 1
    slot0 = next(iter(server.sessions.values())).slot

    # 靜默超過 timeout → 斷線
    for _ in range(int(3.0 / DT)):
        clock.advance(DT)
        server.step(DT)
    assert len(server.sessions) == 0
    assert slot0 in server.free_slots

    # 新客戶端可重用槽位
    cl2 = GameClient(transport=ep, server_addr="server", clock=clock)
    cl2.send_input(MoveInput())
    clock.advance(DT)
    sim.flush()
    server.step(DT)
    assert len(server.sessions) == 1
    assert next(iter(server.sessions.values())).slot == slot0


# --------------------------------------------------------------------- #
# 5. 無損回放（驗收標準）
# --------------------------------------------------------------------- #
def test_lossless_replay_bit_exact():
    clock, sim, server, clients = build_harness(latency=0.03, seed=5, n_clients=2)
    ticks = 512
    live_log = run_script(clock, sim, server, clients, moving_script(ticks), ticks)
    ingest = list(server.ingest_log)      # (tick, addr, data)

    # 全新伺服器（無傳輸層）依 ingest_log 重放
    # 重要：必須同步推進時鐘 —— 反作弊依時間戳驗證輸入速率，
    # 時鐘卡住會讓「同時間戳的大量輸入」被誤判為洪水（正確行為）。
    clock2 = VirtualClock()
    server2 = GameServer(world=World(), transport=None, clock=clock2)
    replay_log = []
    for t in range(ticks):
        for (itick, addr, data) in ingest:
            if itick == t:
                server2.ingest(addr, data)
        clock2.advance(DT)
        server2.step(DT)
        replay_log.append(tuple((p.slot, p.pos.x, p.pos.y, p.pos.z) for p in server2.world.states()))

    assert replay_log == live_log        # 逐 tick 位元級一致
    assert server2.tick == ticks
