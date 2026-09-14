"""工具鏈：程序化地圖編輯器測試（生成 / 驗證 / 匯出 / 進遊戲）。"""

import math

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from tools.maps.export import dict_to_map, load_map, map_to_dict, save_map
from tools.maps.generator import generate_map, validate_map


def test_generate_deterministic():
    a, b = generate_map(seed=5), generate_map(seed=5)
    assert map_to_dict(a) == map_to_dict(b)
    assert len(a.walls) == len(b.walls)


def test_different_seeds_differ():
    a, b = generate_map(seed=5), generate_map(seed=6)
    assert map_to_dict(a) != map_to_dict(b)


def test_map_structure():
    m = generate_map(seed=1)
    assert len(m.sites) == 2
    assert {s.name for s in m.sites} == {"A", "B"}
    assert len(m.spawns_attackers) == 5
    assert len(m.spawns_defenders) == 5
    assert len(m.walls) > 10                     # 有掩體


def test_validate_passes_for_many_seeds():
    for seed in range(1, 30):
        m = generate_map(seed=seed)
        ok, issues = validate_map(m)
        assert ok, f"seed={seed}: {issues}"


def test_export_round_trip(tmp_path):
    m = generate_map(seed=3)
    path = str(tmp_path / "map.json")
    save_map(path, m)
    m2 = load_map(path)
    assert map_to_dict(m) == map_to_dict(m2)


def test_map_usable_in_world():
    """生成的地圖可直接進 World，玩家移動不穿牆。"""
    m = generate_map(seed=7)
    world = World(map_data=m)
    p = world.players[0]
    spawn = m.spawns_attackers[0]
    assert p.pos.distance_to(spawn) < 0.5        # 出生在重生點
    inp = [None] * 10
    inp[0] = MoveInput(forward=1.0)
    # 跑 3 秒 → 不穿過任何牆、不出界
    for _ in range(int(3.0 * 128)):
        world.step(inp, 1 / 128)
    assert m.bounds_min.x < p.pos.x < m.bounds_max.x
    assert m.bounds_min.z < p.pos.z < m.bounds_max.z
    for w in m.walls:
        # 圓柱（半徑 0.35）不與牆重疊
        if p.pos.y + 1.8 > w.mn.y and p.pos.y < w.mx.y:
            cx = min(max(p.pos.x, w.mn.x), w.mx.x)
            cz = min(max(p.pos.z, w.mn.z), w.mx.z)
            assert (p.pos.x - cx) ** 2 + (p.pos.z - cz) ** 2 >= 0.35 ** 2 - 0.05


def test_sites_reachable():
    """點位至少有三個開放方向（可被攻入）。"""
    m = generate_map(seed=11)
    for s in m.sites:
        open_dir = 0
        for d in (Vec3(1, 0, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1), Vec3(0, 0, -1)):
            probe = s.center + d * 4.0
            if m.raycast(s.center + Vec3(0, 1, 0), d, 4.0) is None:
                open_dir += 1
        assert open_dir >= 3, f"site {s.name} 過於封閉"
