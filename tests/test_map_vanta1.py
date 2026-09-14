"""VANTA-1 地圖保證測試：密封性 / 可達性 / 站點與 AI 相容性。"""

import os
import sys

from server.core.math_core import Vec3
from server.game.map_vanta1 import build_vanta1, validate_vanta1

_WORKERS_SRC = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "workers", "src"))


def test_validation_passes():
    res = validate_vanta1()
    assert all(res["reachable_from_atk"].values()), res
    assert res["sealed"], res
    assert res["spots_clear"], res
    assert 800 < res["area_m2"] < 1400, f"可走面積異常: {res['area_m2']}"


def test_sites_match_ai_brain_constants():
    """AI 大腦硬編碼 A_SITE=(12,0,10) → 地圖 A 點必須一致，否則 bot 卡牆。"""
    m = build_vanta1()
    a = m.site_named("A")
    b = m.site_named("B")
    assert a is not None and b is not None
    assert (a.center.x, a.center.z) == (12, 10)
    assert (b.center.x, b.center.z) == (-12, 10)

    if os.path.isdir(_WORKERS_SRC):
        sys.path.insert(0, _WORKERS_SRC)
        import ai_bots
        assert ai_bots.A_SITE.distance_to(a.center) < 0.01
        # 守方卡點必須在地圖內且可行走（不在牆裡）
        for i, h in enumerate(ai_bots.DEFENDER_HOLDS):
            hit = None
            for wl in m.walls:
                if (wl.mn.x <= h.x <= wl.mx.x and wl.mn.z <= h.z <= wl.mx.z
                        and wl.mn.y <= 1.0 and wl.mx.y >= 2.0):
                    hit = wl
                    break
            assert hit is None, f"DEFENDER_HOLDS[{i}] {h} 在牆裡: {hit}"


def test_no_narrow_gaps():
    """不得存在 0.05~0.75m 的牆間縫（玩家直徑 0.7m：卡住/抖動/視線破洞帶）。

    ≥0.75m 的縫視為可走窄道（合法），<0.05 視為貼合。
    """
    m = build_vanta1()
    tall = [w for w in m.walls if w.mx.y >= 1.9]
    bad = []
    for i, a in enumerate(tall):
        for b in tall[i + 1:]:
            ov_z = min(a.mx.z, b.mx.z) - max(a.mn.z, b.mn.z)
            dx = max(b.mn.x - a.mx.x, a.mn.x - b.mx.x)
            if 0.05 < dx <= 0.75 and ov_z >= 0.3:
                bad.append(("x", round(dx, 2), a, b))
            ov_x = min(a.mx.x, b.mx.x) - max(a.mn.x, b.mn.x)
            dz = max(b.mn.z - a.mx.z, a.mn.z - b.mx.z)
            if 0.05 < dz <= 0.75 and ov_x >= 0.3:
                bad.append(("z", round(dz, 2), a, b))
    assert not bad, f"{len(bad)} 處窄縫: {[(g[0], g[1], g[2].mn, g[3].mn) for g in bad[:5]]}"


def test_spawn_sightlines_blocked():
    """雙方出生點之間不得有直線視線（特戰原則：出生即安全）。"""
    m = build_vanta1()
    for ap in m.spawns_attackers:
        for dp in m.spawns_defenders:
            eye_a = ap + Vec3(0, 1.6, 0)
            eye_d = dp + Vec3(0, 1.6, 0)
            assert not m.los_clear(eye_a, eye_d), \
                f"攻 {ap} 與守 {dp} 互相看得見！"


def test_legacy_map_still_loads():
    from server.game.mapdata import _legacy_default_map, default_map
    legacy = _legacy_default_map()
    assert len(legacy.walls) > 0
    cur = default_map()
    assert any(s.name == "A" for s in cur.sites)
