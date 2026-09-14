"""M4/M5/M6/M14：幾何、地圖、武器、後座力、彈道與傷害測試。"""

import math

import pytest

from server.core.math_core import Vec3
from server.game.ballistics import (
    HIT_REGIONS,
    Projectile,
    explode,
    hit_test_entity,
    resolve_hitscan,
)
from server.game.geometry import ray_vs_aabb, ray_vs_capsule, ray_vs_sphere, segment_sphere_hit
from server.game.mapdata import SmokeCloud, default_map
from server.game.recoil import PATTERNS, RecoilController, SpreadEngine, pattern_for
from server.game.weapons import damage_at, weapon

import random


# --------------------------------------------------------------------- #
# 幾何
# --------------------------------------------------------------------- #
def test_ray_sphere():
    o, d = Vec3(0, 0, 0), Vec3(0, 0, 1)
    assert math.isclose(ray_vs_sphere(o, d, Vec3(0, 0, 5), 1.0, 100), 4.0)
    assert ray_vs_sphere(o, d, Vec3(0, 3, 5), 1.0, 100) is None      # 偏離
    assert ray_vs_sphere(o, d, Vec3(0, 0, 5), 1.0, 3.0) is None      # 超出 max_dist


def test_ray_capsule_hits_body():
    o, d = Vec3(0, 1.6, 0), Vec3(0, 0, 1)
    a, b = Vec3(0, 0.5, 8), Vec3(0, 1.6, 8)
    t = ray_vs_capsule(o, d, a, b, 0.34, 100)
    assert t is not None and 7.0 < t < 8.0


def test_ray_aabb():
    o, d = Vec3(0, 1, 0), Vec3(1, 0, 0)
    hit = ray_vs_aabb(o, d, Vec3(5, 0, -1), Vec3(6, 3, 1), 100)
    assert hit is not None and math.isclose(hit[0], 5.0)
    assert hit[1] == Vec3(-1, 0, 0)     # 法線朝內
    assert ray_vs_aabb(o, d, Vec3(5, 4, -1), Vec3(6, 5, 1), 100) is None


def test_segment_sphere():
    assert segment_sphere_hit(Vec3(0, 0, 0), Vec3(10, 0, 0), Vec3(5, 0, 0), 1.0)
    assert not segment_sphere_hit(Vec3(0, 0, 0), Vec3(10, 0, 0), Vec3(5, 3, 0), 1.0)


# --------------------------------------------------------------------- #
# 地圖
# --------------------------------------------------------------------- #
def test_map_raycast_wall():
    m = default_map()
    hit = m.raycast(Vec3(0, 1, -25), Vec3(0, 0, 1), 100)
    assert hit is not None and hit.wall.material == "unbreakable"
    assert hit.dist < 6.0


def test_map_los():
    from server.game.mapdata import Wall

    m = default_map()
    # A Main 走廊直線通暢（x=13.5 在 main 口 x[11,16] 內）
    assert m.los_clear(Vec3(13.5, 1, -4), Vec3(13.5, 1, 1))
    # 同一射線延伸進站點 → 被 Gen 箱（11.5..14.5, 3..5.5）阻擋
    assert not m.los_clear(Vec3(13.5, 1, 0), Vec3(13.5, 1, 8))
    # 動態加牆仍可阻擋
    m.walls.append(Wall(Vec3(0, 0, -9), Vec3(0.2, 4, -8.8), "concrete"))
    assert not m.los_clear(Vec3(0, 1, -12), Vec3(0, 1, -7))


def test_smoke_blocks_segment():
    s = SmokeCloud(Vec3(0, 2, 5), 3.0, 15.0, rng=random.Random(1))
    assert s.blocks_segment(Vec3(0, 1, 0), Vec3(0, 1, 10))
    assert not s.blocks_segment(Vec3(20, 1, 0), Vec3(20, 1, 10))
    s.update(16.0)
    assert not s.active


# --------------------------------------------------------------------- #
# 武器
# --------------------------------------------------------------------- #
def test_weapon_catalogue():
    for key in ("vandal", "phantom", "ghost", "operator", "classic", "spectre", "odin"):
        assert weapon(key).price >= 0
    assert weapon("vandal").damage == 40
    assert weapon("operator").damage == 150
    assert weapon("outlaw").damage == 140
    assert weapon("bandit").price == 600
    assert weapon("phantom").wclass == "rifle"


def test_damage_falloff():
    phantom = weapon("phantom")
    assert damage_at(phantom, 0) == 39
    assert damage_at(phantom, 15) == 39
    # Phantom 衰減 0-15m 全傷 39, 15-50m 線性衰減到 31
    assert damage_at(phantom, 50) == 31
    assert damage_at(phantom, 100) == 31
    # 中間值線性（32.5m → 35）
    mid = damage_at(phantom, 32.5)
    assert math.isclose(mid, 35.0, rel_tol=0.02)
    # 無衰減武器
    assert damage_at(weapon("vandal"), 200) == 40


# --------------------------------------------------------------------- #
# 後座力與擴散
# --------------------------------------------------------------------- #
def test_recoil_pattern_deterministic_and_protected():
    rng = random.Random(7)
    pat = PATTERNS["vandal"]
    ctrl = RecoilController(pat, rng)
    kicks = [ctrl.fire(0.0) for _ in range(pat.protected_bullets)]
    # 保護彈：完全確定（與圖案一致）
    for i, (p, y) in enumerate(kicks):
        assert math.isclose(p, pat.pitch_deg[i], rel_tol=1e-9)
        assert math.isclose(y, pat.yaw_deg[i], rel_tol=1e-9)
    # 之後 yaw 隨機化：不同 rng 種子 → 不同結果
    rng2 = random.Random(8)
    c2 = RecoilController(pat, rng2)
    for _ in range(pat.protected_bullets):
        c2.fire(0.0)
    _, y_a = ctrl.fire(0.0)
    _, y_b = c2.fire(0.0)
    assert y_a != y_b


def test_recoil_recovery():
    rng = random.Random(1)
    ctrl = RecoilController(PATTERNS["vandal"], rng)
    ctrl.fire(0.0)
    assert ctrl.pitch > 0.0
    # 未過 reset_time → 不恢復
    ctrl.update(0.5, 1 / 128)
    assert ctrl.pitch > 0.0
    # 過 reset_time 後恢復至 0
    for _ in range(200):
        ctrl.update(3.0, 1 / 128)
    assert ctrl.fully_recovered()


def test_spread_engine():
    rng = random.Random(3)
    se = SpreadEngine(rng)
    v = weapon("vandal")
    # 首發靜止 → 極小擴散
    s0 = se.spread_deg(v, 0.0, 0, False, False, False)
    assert s0 == pytest.approx(v.first_shot_accuracy)
    # 擴散隨彈數成長
    s10 = se.spread_deg(v, 0.0, 10, False, False, False)
    assert s10 > s0
    # 移動誤差疊加、ADS 減半
    sm = se.spread_deg(v, 2.4, 0, False, False, False)
    sads = se.spread_deg(v, 2.4, 0, False, True, False)
    assert sm > s0
    assert sads < sm
    # 採樣方向落在圓錐內（與原方向夾角 <= spread）
    d = se.sample_dir(Vec3(0, 0, 1), 5.0)
    angle = math.degrees(math.acos(max(-1, min(1, d.dot(Vec3(0, 0, 1))))))
    assert angle <= 5.0 + 1e-6
    # 零擴散 → 原方向
    assert se.sample_dir(Vec3(0, 0, 1), 0.0) == Vec3(0, 0, 1)


# --------------------------------------------------------------------- #
# 彈道與傷害
# --------------------------------------------------------------------- #
def test_hitbox_multipliers():
    assert [r.multiplier for r in HIT_REGIONS] == [4.0, 1.0, 0.85]
    assert HIT_REGIONS[0].name == "head"


def test_entity_hit_test_head():
    # 瞄準頭部（y=1.80，高於身體膠囊頂帽）→ 命中頭部區域
    hit = hit_test_entity(Vec3(0, 1.6, 0), (Vec3(0, 1.80, 8) - Vec3(0, 1.6, 0)).normalized(),
                          Vec3(0, 0, 8), 100)
    assert hit is not None
    assert hit[1].name == "head"
    # 瞄身體（y=1.0）→ 不會命中頭
    hit2 = hit_test_entity(Vec3(0, 1.6, 0), (Vec3(0, 1.0, 8) - Vec3(0, 1.6, 0)).normalized(),
                           Vec3(0, 0, 8), 100)
    assert hit2 is not None and hit2[1].name != "head"


def _mk_world():
    from server.game.entities import World

    return World()


def _clear_others(world, keep=(0, 1)):
    """將非測試目標的玩家移到遠方，避免擋住射線。"""
    for i, p in enumerate(world.players):
        if i not in keep:
            p.pos = Vec3(0, -50, 0)


def test_resolve_body_shot_and_kill():
    world = _mk_world()
    _clear_others(world)
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[1].pos = Vec3(0, 0, 8)
    origin = Vec3(0, 1.6, 0)
    dirv = (Vec3(0, 0.55, 8) - origin).normalized()     # 瞄身體
    res = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("vandal"), None)
    assert len(res.hits) == 1
    assert res.hits[0].target_slot == 1
    assert res.hits[0].region in ("body", "legs")
    assert res.hits[0].final_damage > 0
    assert world.players[1].health < 100.0


def test_headshot_four_times():
    world = _mk_world()
    _clear_others(world)
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[1].pos = Vec3(0, 0, 8)
    origin = Vec3(0, 1.6, 0)
    dirv = (Vec3(0, 1.80, 8) - origin).normalized()     # 瞄頭（高於身體膠囊頂帽）
    res = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("vandal"), None)
    assert res.hits and res.hits[0].region == "head"
    assert math.isclose(res.hits[0].final_damage, 160.0)
    assert world.players[1].health == 0.0               # 一槍爆頭死
    assert not world.players[1].alive


def test_wall_penetration():
    from server.game.mapdata import MATERIALS, Wall

    world = _mk_world()
    _clear_others(world)
    # 移除預設混凝土掩體，只留測試牆
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.map_data.walls.append(Wall(Vec3(0, 0, 4), Vec3(0.2, 4, 4.2), "wood"))  # 薄木牆
    world.players[1].pos = Vec3(0, 0, 8)
    origin = Vec3(0, 1.6, 0)
    dirv = (Vec3(0, 1.3, 8) - origin).normalized()      # 瞄身體中段
    # 手槍 (pen 0) 穿不過木牆 (需 pen1)
    res = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("classic"), None)
    assert res.hits == []
    assert res.wall_hits == 0
    # 步槍 (pen 2) 穿過 → 傷害 ×0.8
    res2 = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("vandal"), None)
    assert len(res2.hits) == 1
    assert res2.wall_hits == 1
    assert math.isclose(res2.hits[0].final_damage, 40 * 0.8, rel_tol=0.05)


def test_unbreakable_wall_blocks():
    world = _mk_world()
    _clear_others(world)
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[1].pos = Vec3(0, 0, 8)
    origin = Vec3(0, 1.6, 0)
    dirv = (Vec3(0, 1.3, 8) - origin).normalized()
    res = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("vandal"), None)
    # 沒牆可打 → 命中
    assert len(res.hits) == 1
    # 加一道不可穿透牆
    from server.game.mapdata import Wall

    world.map_data.walls.append(Wall(Vec3(0, 0, 5), Vec3(0.2, 4, 5.2), "unbreakable"))
    res2 = resolve_hitscan(world, world.map_data, 0, origin, dirv, weapon("vandal"), None)
    assert res2.hits == []


def test_projectile_parabola_and_bounce():
    m = default_map()
    p = Projectile(Vec3(0, 8, 0), Vec3(0, 0, 5), 0, gravity=9.8, max_bounces=2)   # y=8：飛越中路建築
    max_z = 0.0
    for _ in range(400):
        p.step(1 / 128, m)
        max_z = max(max_z, p.pos.z)
    assert max_z > 5.0                    # 有向前拋物線飛行
    # 垂直下拋 → 地面反彈
    p2 = Projectile(Vec3(0, 8, 0), Vec3(0, -10, 0), 0, max_bounces=1)
    bounced = False
    for _ in range(300):
        if p2.step(1 / 128, m) == "wall_bounce":
            bounced = True
            break
    assert bounced
    assert p2.vel.y > 0.0                 # 反彈後向上


def _fire_rapid(world, slot, yaw, pitch):
    """開一槍並推進射速間隔（fire_shot 有射速冷卻）。"""
    hits = world.fire_shot(slot, yaw, pitch)
    world.time += 0.2          # > classic/vandal 射速間隔 → 允許連續開火
    return hits


def test_recoil_accumulates_without_compensation():
    """連射不壓槍 → 後座力偏移持續累積（準星不動，彈道漂移）。"""
    world = _mk_world()
    _clear_others(world)
    p = world.players[0]
    for _ in range(10):
        _fire_rapid(world, 0, 0.0, 0.0)        # 準星固定不動
    assert p.weapon.aim_pitch_offset > 5.0     # 垂直後座力明顯累積
    assert p.weapon.aim_yaw_offset != 0.0      # 水平後座力也偏移


def test_recoil_compensation_keeps_hits():
    """壓槍（抵銷累積後座力偏移）→ 連射仍能持續命中並擊殺。"""
    world = _mk_world()
    _clear_others(world)
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[0].pos = Vec3(0, 0, 0)      # 射擊點（混凝土牆已移除 → 開闊）
    world.players[1].pos = Vec3(0, 0, 8)
    p = world.players[0]
    base_pitch = math.degrees(math.atan2(1.0 - 1.6, 8.0))   # 瞄身體
    for _ in range(12):
        _fire_rapid(world, 0, 0.0, base_pitch - p.weapon.aim_pitch_offset)
        if not world.players[1].alive:
            break
    assert not world.players[1].alive          # 壓槍下 12 發內必定擊殺


def test_recoil_without_compensation_shot_goes_high():
    """不壓槍 → 累積偏移使彈道高過目標頭頂（必然脫靶）。"""
    world = _mk_world()
    _clear_others(world)
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[1].pos = Vec3(0, 0, 8)
    p = world.players[0]
    for _ in range(8):
        _fire_rapid(world, 0, 0.0, 0.0)
    ray_y_at_target = math.tan(math.radians(p.weapon.aim_pitch_offset)) * 8.0 + 1.6
    assert ray_y_at_target > 1.9               # 高過頭部頂端 1.85 → 脫靶


def test_explosion_radius_damage():
    world = _mk_world()
    world.map_data.walls = [w for w in world.map_data.walls if w.material != "concrete"]
    world.players[5].pos = Vec3(5, 0, 0)     # 敵方（team1）在爆炸半徑內
    world.players[6].pos = Vec3(40, 0, 40)   # 太遠
    victims = explode(world, world.map_data, Vec3(0, 0, 0), 15.0, 90.0, team=0)
    assert 5 in victims and 6 not in victims
    assert world.players[5].health < 100.0
    assert world.players[6].health == 100.0
