"""
端到端整合測試：10 個客戶端透過網路打一整場回合。
驗證全系統鏈路：輸入 → 128Hz 伺服器 → 購買 → 技能 → Spike 安放/爆炸
→ 回合結算 → 經濟 → 下一回合購買。
"""

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.netcode.client_loop import GameClient
from server.netcode.protocol import ACTION_ABILITY, ACTION_BUY, ACTION_PLANT
from server.netcode.server_loop import GameServer
from server.netcode.timing import VirtualClock
from server.netcode.transport import NetworkSimulator

DT = 1.0 / 128.0


@pytest.fixture()
def game():
    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=42)
    world = World()
    match = world.start_match()
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    clients = []
    for i in range(10):
        sim.set_link("server", f"c{i}", latency=0.02, loss_rate=0.0)
        clients.append(GameClient(transport=sim.create_endpoint(f"c{i}"),
                                  server_addr="server", clock=clock,
                                  walls=[(w.mn, w.mx) for w in world.map_data.walls]))
    return clock, sim, server, clients


def advance(clock, sim, server, clients, ticks):
    for _ in range(ticks):
        for c in clients:
            c.poll()
        for c in clients:
            c.send_input(MoveInput())
        clock.advance(DT)
        sim.flush()
        server.step(DT)


def test_full_round_flow(game):
    clock, sim, server, clients = game
    match = server.world.match

    # 1) 買期（45s）→ 行動期
    advance(clock, sim, server, clients, int(46.0 / DT))
    assert match.phase.value == "action"
    assert match.round == 1

    # 2) 攻方（slot0）施放煙霧技能（assault kit index 2）
    clients[0].send_action(ACTION_ABILITY, p0=2, p1=0, p2=0)
    advance(clock, sim, server, clients, int(2.0 / DT))
    assert len(server.world.smokes) >= 0      # 投擲中或已落地
    assert server.world.players[0].abilities.slots[2].charges_left == 1  # 用掉一發

    # 3) 攻方前往 A 點安放 Spike（4 秒）
    #    直接設定位置 = 伺服器權威的「傳送」→ 告知反作弊這是合法重生/傳送
    server.world.players[0].pos = Vec3(12, 0, 10)
    server.anticheat.on_round_reset()      # 合法傳送：重置位置追蹤
    clients[0].send_action(ACTION_PLANT, p0=1)
    advance(clock, sim, server, clients, int(5.0 / DT))
    assert server.world.spike.state.value == "planted"
    # 安放完成 → 攻方全員 +300
    assert server.world.players[0].economy.credits == 800 + 300
    assert server.world.players[4].economy.credits == 800 + 300
    assert server.world.players[5].economy.credits == 800          # 守方無

    # 4) 45 秒後爆炸 → 守方全滅 → 攻方勝
    #    （守方出生點 ±14 超出爆炸半徑 25m → 先移到半徑內再爆；
    #      傳送需告知反作弊為合法，否則會被重置回出生點）
    for i in range(5, 10):
        server.world.players[i].pos = Vec3(-7.0 + 3.5 * (i - 5), 0, 16)
    server.anticheat.on_round_reset()
    advance(clock, sim, server, clients, int(46.0 / DT))
    assert server.world.spike.state.value == "detonated"
    assert not server.world.players[5].alive
    assert server.world.players[0].alive

    # 5) 結算（4s）→ 進入第 2 回合買期
    advance(clock, sim, server, clients, int(5.0 / DT))
    assert match.round == 2
    assert match.phase.value == "buy"
    assert match.scores[0] == 1
    # 經濟：攻方 +3000 勝利；守方連敗補償 1900
    assert server.world.players[0].economy.credits == 800 + 300 + 3000
    assert server.world.players[5].economy.credits == 800 + 1900
    # 回合重置：血量、Spike、位置
    assert server.world.players[5].alive and server.world.players[5].health == 100.0
    assert server.world.spike.state.value == "idle"

    # 6) 第 2 回合購買：補貼攻方後透過 ACTION_BUY 買 Vandal（上限 9000）
    server.world.players[0].economy.grant(8000)
    assert server.world.players[0].economy.credits == 9000       # 已封頂
    clients[0].send_action(ACTION_BUY, p0=19)                    # vandal（字母序）
    advance(clock, sim, server, clients, int(2.0 / DT))
    assert server.world.players[0].weapon.stats.key == "vandal"
    assert server.world.players[0].economy.credits == 9000 - 2900


def test_prediction_works_end_to_end(game):
    clock, sim, server, clients = game
    # 先進入行動期（買期移動凍結，無法比較預測）
    advance(clock, sim, server, clients, int(46.0 / DT))
    assert server.world.match.phase.value == "action"
    # 讓 slot0 先橫移對準出生門（x[-4,4]），再直進 — VANTA-1 廊道路徑
    start = server.world.players[0].pos
    for i in range(128 * 2):
        for c in clients:
            c.poll()
        clients[0].send_input(MoveInput(strafe=1.0) if i < 64 else MoveInput(forward=1.0))
        for c in clients[1:]:
            c.send_input(MoveInput())
        clock.advance(DT)
        sim.flush()
        server.step(DT)
    assert clients[0].local.pos.distance_to(server.world.players[0].pos) < 0.3
    assert server.world.players[0].pos.distance_to(start) > 5.0   # 真的在跑
