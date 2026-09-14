"""地圖佈局（特戰英豪風格）：出生視線、房間封閉、點位、門寬、驗證。"""

from server.core.math_core import Vec3
from server.game.mapdata import default_map
from tools.maps.generator import validate_map
from tools.maps.export import map_to_dict


def test_validate_default_map():
    ok, issues = validate_map(default_map())
    assert ok, issues


def test_no_los_between_spawns():
    """雙方任何出生點之間都不可直接看到對方（特戰核心規則）。"""
    m = default_map()
    for a in m.spawns_attackers:
        for b in m.spawns_defenders:
            eye = a + Vec3(0, 1.6, 0)
            assert not m.los_clear(eye, b + Vec3(0, 1.6, 0)), f"{a} → {b} 可直接對視"


def test_spawns_enclosed_in_rooms():
    """出生點在建築內：門被牆擋住，出生看不到場中。"""
    m = default_map()
    for a in m.spawns_attackers:
        eye = a + Vec3(0, 1.6, 0)
        assert not m.los_clear(eye, Vec3(0, 1.6, 0)), f"{a} 可直視場中"
    for b in m.spawns_defenders:
        eye = b + Vec3(0, 1.6, 0)
        assert not m.los_clear(eye, Vec3(0, 1.6, 0)), f"{b} 可直視場中"


def test_sites_and_bounds_preserved():
    m = default_map()
    assert {s.name for s in m.sites} == {"A", "B"}
    assert m.site_named("A").center == Vec3(12, 0, 10)
    assert m.site_named("B").center == Vec3(-12, 0, 10)
    for w in m.walls:
        assert m.bounds_min.x - 1 <= w.mn.x and w.mx.x <= m.bounds_max.x + 1
        assert m.bounds_min.z - 1 <= w.mn.z and w.mx.z <= m.bounds_max.z + 1


def test_spawn_doors_walkable():
    """VANTA-1 所有門/缺口中心不被牆佔住（玩家直徑 0.7 + 餘裕）。"""
    m = default_map()
    doors = [
        (0.0, -13.3),     # 攻方出生正面門
        (-8.3, -9.0), (8.3, -9.0),    # tiles ↔ 大廳門
        (-8.3, 4.0), (8.3, 4.0),      # courtyard → site Link 缺口
        (-3.5, -6.0),     # tiles → courtyard（錯位門 x[-6,-1]）
        (3.5, 6.0),       # courtyard → mid top（反向錯位門 x[1,6]）
        (-12.0, 13.3), (12.0, 13.3),  # 站點迴防缺口
        (0.0, 13.0),      # mid top → CT
    ]
    for dx, dz in doors:
        door_center = Vec3(dx, 0, dz)
        for w in m.walls:
            if w.mn.y > 1.0 or w.mx.y < 3.0:
                continue
            cx = min(max(door_center.x, w.mn.x), w.mx.x)
            cz = min(max(door_center.z, w.mn.z), w.mx.z)
            d2 = (door_center.x - cx) ** 2 + (door_center.z - cz) ** 2
            assert d2 > 0.7 * 0.7, f"門 ({dx},{dz}) 被牆卡住: {w}"


def test_serialization_roundtrip():
    """新地圖可序列化 → 客戶端渲染與伺服器碰撞一致。"""
    d = map_to_dict(default_map())
    assert d["sites"][0]["center"]["x"] == 12.0
    assert len(d["walls"]) >= 30
    assert all(w["material"] in ("concrete", "wood", "metal", "unbreakable") for w in d["walls"])