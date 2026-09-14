"""M2 記憶體網路（延遲/遺失/抖動）測試。"""

from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator


def make_net(seed=7):
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=seed)
    a = sim.create_endpoint("a")
    b = sim.create_endpoint("b")
    return sim, clock, a, b


def test_zero_latency_immediate_delivery():
    sim, clock, a, b = make_net()
    a.send_to(b"hello", "b")
    assert b.recv_from() == []            # 尚未 flush
    sim.flush()
    got = b.recv_from()
    assert got == [("a", b"hello")]


def test_latency_delays_delivery():
    sim, clock, a, b = make_net()
    sim.set_link("a", "b", latency=0.1)
    a.send_to(b"x", "b")
    clock.advance(0.05)
    sim.flush()
    assert b.recv_from() == []            # 尚未到期
    clock.advance(0.05)                   # 共 0.1s
    sim.flush()
    assert b.recv_from() == [("a", b"x")]


def test_full_loss_drops_everything():
    sim, clock, a, b = make_net()
    sim.set_link("a", "b", latency=0.0, loss_rate=1.0)
    for i in range(10):
        a.send_to(bytes([i]), "b")
    sim.flush()
    assert b.recv_from() == []


def test_loss_is_deterministic_and_partial():
    """相同種子 → 相同遺失模式；0.3 遺失率 → 有收有失。"""
    sim, clock, a, b = make_net(seed=123)
    sim.set_link("a", "b", latency=0.001, loss_rate=0.3)
    sent = 100
    for i in range(sent):
        a.send_to(bytes([i]), "b")
        clock.advance(0.001)
        sim.flush()
    got = {d[1][0] for d in b.recv_from()}   # (src, data) → 取 data 首 byte
    assert len(got) > 0 and len(got) < sent      # 部分到達

    # 重跑相同種子 → 完全相同的遺失集合（端點 id 仍為 a/b）
    sim2, clock2, a2, b2 = make_net(seed=123)
    sim2.set_link("a", "b", latency=0.001, loss_rate=0.3)
    for i in range(sent):
        a2.send_to(bytes([i]), "b")
        clock2.advance(0.001)
        sim2.flush()
    got2 = {d[1][0] for d in b2.recv_from()}
    assert got == got2


def test_order_preserved_with_latency():
    """固定延遲下，封包以發送順序交付。"""
    sim, clock, a, b = make_net()
    sim.set_link("a", "b", latency=0.05)
    for i in range(20):
        a.send_to(bytes([i]), "b")
    clock.advance(0.2)
    sim.flush()
    order = [d[1][0] for d in b.recv_from()]   # (src, data) → data 首 byte 序號
    assert order == list(range(20))
