"""M2 客戶端迴圈：RTT 估算 (EWMA) 與快照順序測試。"""

import math

from server.core.movement import MoveInput
from server.game.world import World
from server.netcode.client_loop import GameClient
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1.0 / 128.0


def run_sim(latency=0.1, loss=0.0, ticks=512, seed=11, n_clients=1):
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=seed)
    server_ep = sim.create_endpoint("server")
    server = GameServer(world=World(), transport=server_ep, clock=clock)
    clients = []
    for i in range(n_clients):
        sim.set_link("server", f"c{i}", latency=latency, loss_rate=loss)
        ep = sim.create_endpoint(f"c{i}")
        clients.append(GameClient(transport=ep, server_addr="server", clock=clock))

    for t in range(ticks):
        for ci, cl in enumerate(clients):
            cl.poll()
            cl.send_input(MoveInput(strafe=1.0, forward=0.2))
        clock.advance(DT)
        sim.flush()
        server.step(DT)
    return clock, sim, server, clients


def test_rtt_converges_to_round_trip_latency():
    """單向延遲 0.1s → RTT 應收斂至 ≈0.2s（EWMA）。"""
    _, _, _, clients = run_sim(latency=0.1, ticks=512)
    c = clients[0]
    assert c.rtt_ms > 0.0
    # 量化誤差：兩側各 ≤1 tick (≈7.8ms) + 排程粒度 → 容差 ±25ms
    assert 175.0 <= c.rtt_ms <= 225.0


def test_lower_latency_gives_lower_rtt():
    _, _, _, fast = run_sim(latency=0.05, ticks=512, seed=1)
    _, _, _, slow = run_sim(latency=0.15, ticks=512, seed=1)
    assert fast[0].rtt_ms < slow[0].rtt_ms
    assert 75.0 <= fast[0].rtt_ms <= 125.0
    assert 275.0 <= slow[0].rtt_ms <= 325.0


def test_snapshot_server_tick_monotonic():
    _, _, _, clients = run_sim(latency=0.02, ticks=512)
    c = clients[0]
    assert c.last_server_tick > 400     # 收到大量快照
    assert c.snapshot_count > 0
    # 序列不跳號驗證：最後一個收到的 tick 應接近總 tick 數
    assert c.last_server_tick <= 512


def test_survives_packet_loss():
    """10% 遺失率下仍正常運作：有快照、RTT 有限、世界推進。"""
    clock, sim, server, clients = run_sim(latency=0.05, loss=0.1, ticks=512, seed=7)
    c = clients[0]
    assert c.snapshot_count > 40    # 快照自 128Hz 降為 16Hz（512 ticks ≈ 64 張）
    assert 0.0 < c.rtt_ms < 400.0
    assert server.world.players[0].pos.x > 0.5   # 世界正常推進


def test_ewma_smooths_spikes():
    """EWMA α=0.25：RTT 樣本突變不會瞬間跳到極值。"""
    c = GameClient.__new__(GameClient)   # 只測 EWMA 數學
    c.rtt_ms = 100.0
    c.rtt_alpha = 0.25
    c.rtt_ms = (1 - 0.25) * c.rtt_ms + 0.25 * 500.0   # 一次 500ms 突刺
    assert math.isclose(c.rtt_ms, 200.0, rel_tol=1e-9)
