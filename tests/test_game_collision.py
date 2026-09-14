"""M14 強化：移動碰撞測試（牆面擋停、沿牆滑移、玩家推離、地圖邊界）。"""

import math

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.game.mapdata import Wall, default_map

DT = 1.0 / 128.0
R = 0.35   # 玩家半徑


def step(world, seconds, inputs=None):
    for _ in range(int(seconds / DT)):
        world.step(inputs if inputs is not None else [None] * 10, DT)


def test_blocked_by_wall():
    """玩家向前走 → 被牆擋住，停在牆前（半徑距離處），速度歸零。"""
    world = World()
    world.map_data.walls.append(Wall(Vec3(-10, 0, 5), Vec3(10, 4, 5.2), "concrete"))
    world.players[0].pos = Vec3(-6, 0, 0)     # 開闊處（避開中路建築）
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    step(world, 1.5, inp)
    p = world.players[0]
    assert p.pos.z <= 5.0 - R + 0.05        # 停在牆前（z=5 牆面 - 半徑）
    assert abs(p.vel.z) < 0.01              # 速度已被消除
    assert p.pos.z > 4.0                    # 確實有前進


def test_slide_along_wall():
    """斜向撞牆 → 水平分量被消、沿牆滑移仍繼續。"""
    world = World()
    # 沿 Z 軸的長牆
    world.map_data.walls.append(Wall(Vec3(3, 0, -20), Vec3(3.2, 4, 20), "concrete"))
    world.players[0].pos = Vec3(-6, 0, 0)     # 開闊處（避開中路建築）
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0, strafe=1.0)   # 對角線：往 +x 撞牆、+z 前進
    step(world, 2.6, inp)
    p = world.players[0]
    assert p.pos.x <= 3.0 - R + 0.05        # 沒穿牆
    # 對角線水平速率 = 5.4/√2 ≈ 3.8 m/s → 撞牆後滑行
    assert p.pos.z > 3.2                    # 沿牆向前滑移


def test_players_push_apart():
    """兩名玩家同一位置 → 被推開至半徑和距離。"""
    world = World()
    world.players[0].pos = Vec3(0, 0, 0)
    world.players[1].pos = Vec3(0, 0, 0)
    step(world, 0.2)
    d = world.players[0].pos.distance_to(world.players[1].pos)
    assert d >= 2 * R - 0.05


def test_players_do_not_overlap_after_collision():
    """玩家間碰撞後不可重疊（含移動中）。"""
    world = World()
    world.players[0].pos = Vec3(0, 0, 0)
    world.players[1].pos = Vec3(0.1, 0, 0)
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    inp[1] = MoveInput(forward=1.0)
    step(world, 1.0, inp)
    d = world.players[0].pos.distance_to(world.players[1].pos)
    assert d >= 2 * R - 0.1


def test_cannot_leave_map_bounds():
    """長時間向前跑 → 被外牆擋住，無法出界。"""
    world = World()
    world.players[0].pos = Vec3(0, 0, -5)
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    step(world, 10.0, inp)                  # 10 秒 → 若無牆會跑 54m
    p = world.players[0]
    assert p.pos.z < 20.0                   # 外牆在 z=20
    assert abs(p.vel.z) < 0.01


def test_diagonal_corner_does_not_clip():
    """斜向衝向角落 → 不會卡入牆角（推離在多次迭代中收斂）。"""
    world = World()
    world.map_data.walls.append(Wall(Vec3(5, 0, -10), Vec3(5.2, 4, 10), "concrete"))   # X 牆
    world.map_data.walls.append(Wall(Vec3(-10, 0, 5), Vec3(10, 4, 5.2), "concrete"))   # Z 牆
    world.players[0].pos = Vec3(2, 0, 2)
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0, strafe=1.0)   # 朝角落 (5,5)
    step(world, 1.5, inp)
    p = world.players[0]
    assert p.pos.x <= 5.0 - R + 0.05
    assert p.pos.z <= 5.0 - R + 0.05
    # 沒有被推過任何牆面（仍在合法空間）
    for w in world.map_data.walls:
        assert not (w.mn.x - R < p.pos.x < w.mx.x + R and w.mn.z - R < p.pos.z < w.mx.z + R
                    and w.mn.y < p.pos.y + 1.8 and p.pos.y < w.mx.y)


def test_dead_player_no_collision():
    """死亡的玩家不參與碰撞（屍體不擋路）。"""
    world = World()
    world.players[1].alive = False
    world.players[1].health = 0.0
    world.players[0].pos = Vec3(0, 0, 0)
    world.players[1].pos = Vec3(0.1, 0, 0)
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    step(world, 0.5, inp)
    # 存活玩家可以穿過屍體位置
    assert world.players[0].pos.z > 1.0
