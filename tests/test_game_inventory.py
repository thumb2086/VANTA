"""武器槽位與切換測試（換槍動畫的遊戲邏輯基礎）。"""

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase

DT = 1 / 128.0


def _action_world():
    world = World()
    world.start_match()
    world.match.phase = RoundPhase.ACTION
    return world


def test_default_slots():
    world = World()
    p = world.players[0]
    assert p.inventory.active == 1                 # 預設副武器（classic）
    assert p.weapon.stats.key == "classic"
    assert p.inventory.slots[2].stats.key == "knife"
    assert p.inventory.slots[0] is None            # 主武器空


def test_switch_weapon_blocks_fire():
    world = _action_world()
    p = world.players[0]
    p.economy.grant(9000)
    p.buy_weapon("vandal")                         # 裝主武器並切換
    assert p.inventory.active == 0
    assert p.weapon.stats.key == "vandal"
    # 切換期間不可開火
    assert world.fire_shot(0, 0.0, 0.0) == []
    # 0.65s 後可開火
    for _ in range(int(0.66 / DT)):
        world.step([None] * 10, DT)
    p.weapon.mag = 25                              # 確保有彈
    world.players[0].pos = Vec3(0, 0, -5)
    world.players[5].pos = Vec3(0, 0, 5)
    hits = world.fire_shot(0, 0.0, 0.0)
    assert len(hits) >= 1


def test_switch_to_knife_faster():
    world = _action_world()
    p = world.players[0]
    assert p.switch_weapon(2)
    assert p.inventory.active == 2
    assert p.weapon.stats.key == "knife"
    assert not p.switch_weapon(2)                  # 已在刀上


def test_switch_back_to_sidearm():
    world = _action_world()
    p = world.players[0]
    p.switch_weapon(2)
    assert p.switch_weapon(1)
    assert p.weapon.stats.key == "classic"


def test_switch_instantly_available_for_snapshot():
    """切換立即反映在武器槽位（客戶端觸發換槍動畫）。"""
    world = World()
    p = world.players[0]
    p.switch_weapon(2)
    assert p.inventory.active == 2
    assert p.weapon.stats.key == "knife"


def test_each_weapon_keeps_own_mag():
    world = _action_world()
    p = world.players[0]
    p.economy.grant(9000)
    p.buy_weapon("vandal")
    p.weapon.mag = 5
    p.switch_weapon(1)                             # 回手槍
    assert p.weapon.mag == 12                      # classic 自己的彈匣
    p.switch_weapon(0)                             # 回主武器
    assert p.weapon.mag == 5                       # vandal 彈匣保留


def test_buy_assigns_primary_and_activates():
    world = World()
    p = world.players[0]
    p.economy.grant(9000)
    assert p.buy_weapon("phantom")
    assert p.inventory.active == 0
    assert p.weapon.stats.key == "phantom"
    assert p.inventory.slots[1].stats.key == "classic"   # 副武器還在


def test_reset_all_ammo():
    world = _action_world()
    p = world.players[0]
    p.weapon.mag = 0
    p.switch_weapon(2)
    p.weapon.mag = 0
    p.inventory.reset_all()
    assert p.inventory.slots[1].mag == 12
    assert p.inventory.slots[2].mag == 1


def test_switch_via_server_action():
    """ACTION_SWITCH 封包 → 伺服器切換武器（供客戶端 Q/1/2/3 鍵）。"""
    from server.netcode.protocol import ACTION_SWITCH, ActionPacket
    from server.netcode.server_loop import GameServer
    from server.netcode.timing import VirtualClock
    from server.netcode.transport import NetworkSimulator

    clock = VirtualClock()
    sim = NetworkSimulator(clock=clock, seed=1)
    world = World()
    world.start_match()
    server = GameServer(world=world, transport=sim.create_endpoint("server"), clock=clock)
    ep = sim.create_endpoint("c")
    from server.netcode.client_loop import GameClient

    cl = GameClient(transport=ep, server_addr="server", clock=clock)
    # 註冊（送一個輸入讓 session 建立）
    cl.send_input(MoveInput())
    clock.advance(DT)
    sim.flush()
    server.step(DT)
    slot = next(iter(server.sessions.values())).slot
    assert server.world.players[slot].inventory.active == 1
    # 送切刀行動
    cl.send_action(ACTION_SWITCH, p0=2)
    clock.advance(DT)
    sim.flush()
    server.step(DT)
    assert server.world.players[slot].inventory.active == 2
    assert server.world.players[slot].weapon.stats.key == "knife"
