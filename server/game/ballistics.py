"""
server/game/ballistics.py — M6 混合彈道與傷害判定
==================================================
  * Hitbox 分離：頭部 4.0x / 身體 1.0x / 腿部 0.85x（三顆膠囊）。
  * Hitscan：射線 vs 敵人膠囊 + 牆面穿透衰減（材質等級 × 距離衰減）。
  * 拋物線實體彈道 (Projectile)：重力 + 反彈（狙擊/技能彈丸共用）。
  * 爆炸：半徑內線性衰減 + 視線（可關閉，供 Spike 核爆）。
"""

from __future__ import annotations

import math

from dataclasses import dataclass, field

from server.core.math_core import Vec3
from server.game.geometry import ray_vs_capsule
from server.game.mapdata import MATERIALS, MapData
from server.game.weapons import WeaponStats, damage_at

HEAD_MULT = 4.0
BODY_MULT = 1.0
LEGS_MULT = 0.85

EYE_HEIGHT = 1.6


@dataclass(frozen=True, slots=True)
class HitRegion:
    name: str
    multiplier: float
    radius: float
    center: Vec3        # 腳底上方中心
    half_height: float  # 膠囊半高


HIT_REGIONS: tuple[HitRegion, ...] = (
    # 頭：較大且位置較高，確保與身體膠囊頂帽不重疊，可被獨立瞄準
    HitRegion("head", HEAD_MULT, 0.18, Vec3(0, 1.65, 0), 0.20),
    # 身體：胸腔/腹部
    HitRegion("body", BODY_MULT, 0.30, Vec3(0, 1.05, 0), 0.42),
    # 腿部：膝下細柱（特戰式：不打中軀幹高度）
    HitRegion("legs", LEGS_MULT, 0.16, Vec3(0, 0.32, 0), 0.28),
)


def region_capsule(region: HitRegion, feet: Vec3) -> tuple[Vec3, Vec3]:
    c = feet + region.center
    up = Vec3(0, 1, 0)
    return c - up * region.half_height, c + up * region.half_height


def hit_test_entity(
    origin: Vec3, dir: Vec3, feet: Vec3, max_dist: float
) -> tuple[float, HitRegion] | None:
    """射線 vs 敵人所有命中區膠囊，回傳最近 (距離, 區域)。"""
    best = None
    for r in HIT_REGIONS:
        a, b = region_capsule(r, feet)
        t = ray_vs_capsule(origin, dir, a, b, r.radius, max_dist)
        if t is not None and (best is None or t < best[0]):
            best = (t, r)
    return best


@dataclass(slots=True)
class HitEvent:
    target_slot: int
    region: str
    base_damage: float          # 未乘區域倍率前的衰減後傷害
    final_damage: float         # 最終造成傷害（含區域倍率/護甲/易傷）
    penetrated_walls: int


@dataclass(slots=True)
class ShotResult:
    hits: list[HitEvent]
    wall_hits: int
    shooter_weapon: str


def resolve_hitscan(
    world,
    map_data: MapData,
    shooter_slot: int,
    origin: Vec3,
    dir: Vec3,
    stats: WeaponStats,
    target_positions: dict[int, Vec3] | None = None,
    max_dist: float = 150.0,
    max_penetrations: int = 2,
) -> ShotResult:
    """
    伺服器權威的 Hitscan 解析：
      1) 先測「最靠近射線的敵人」（使用 target_positions，可為 Rollback 位置）；
      2) 若敵人在牆之前 → 命中；
      3) 否則測牆 → 可穿透則穿過並衰減，重複，直到無牆或超出次數。
    """
    hits: list[HitEvent] = []
    wall_hits = 0
    pos = origin
    dist_so_far = 0.0
    pen_dmg_mult = 1.0          # 穿透衰減累積倍率

    for _ in range(max_penetrations + 1):
        # 敵人測試（若射手死亡的敵人略過）
        wall_hit = map_data.raycast(pos, dir, max_dist - dist_so_far)
        wall_dist = wall_hit.dist if wall_hit is not None else None

        ent_hit = None
        for slot, feet in (target_positions or _current_positions(world)).items():
            if slot == shooter_slot:
                continue
            p = world.players[slot]
            if not p.alive:
                continue
            hit = hit_test_entity(pos, dir, feet, max_dist - dist_so_far)
            if hit is not None and (ent_hit is None or hit[0] < ent_hit[0]):
                ent_hit = (hit[0], slot, hit[1])

        if ent_hit is not None and (wall_dist is None or ent_hit[0] <= wall_dist):
            t, slot, region = ent_hit
            base = damage_at(stats, dist_so_far + t) * pen_dmg_mult
            final = base * region.multiplier
            p = world.players[slot]
            eff = p.apply_damage(final, source_slot=shooter_slot, weapon_key=stats.key)
            hits.append(HitEvent(slot, region.name, base, eff.damage_dealt, wall_hits))
            break

        if wall_hit is None:
            break
        mat = MATERIALS.get(wall_hit.wall.material)
        if mat is None or stats.penetration_level < mat.required_pen_level:
            break
        # 穿過：累積衰減、推進到「出牆」再繼續
        wall_hits += 1
        pen_dmg_mult *= mat.damage_keep_mult
        dist_so_far += wall_hit.dist + 0.3
        pos = pos + dir * (wall_hit.dist + 0.3)
        if dist_so_far >= max_dist:
            break
    return ShotResult(hits=hits, wall_hits=wall_hits, shooter_weapon=stats.key)


def _current_positions(world) -> dict[int, Vec3]:
    return {i: p.pos for i, p in enumerate(world.players)}


# ---------------------------------------------------------------------- #
# 拋物線實體彈道
# ---------------------------------------------------------------------- #
@dataclass(slots=True)
class Projectile:
    """重力拋物線 + 反彈的實體彈丸（狙擊穿甲彈/技能投擲物共用）。"""

    pos: Vec3
    vel: Vec3
    team: int
    gravity: float = 9.8
    bounce_restitution: float = 0.5
    max_bounces: int = 3
    fuse_time: float | None = None      # None = 無定時（狙擊彈丸）
    damage: float = 0.0
    explosion_radius: float = 0.0
    behavior: str = "hit"               # hit / frag / flash / smoke / spike_shell
    owner_slot: int = -1
    params: dict = field(default_factory=dict)

    def step(self, dt: float, map_data: MapData) -> str | None:
        """推進一幀；回傳事件字串或 None（'wall_bounce'/'detonate'/'expired'）。"""
        if self.fuse_time is not None:
            self.fuse_time -= dt
            if self.fuse_time <= 0.0:
                return "detonate"
        self.vel = Vec3(self.vel.x, self.vel.y - self.gravity * dt, self.vel.z)
        new_pos = self.pos + self.vel * dt
        d = new_pos - self.pos
        dist = d.length()
        if dist < 1e-9:
            return None
        hit = map_data.raycast(self.pos, d.normalized(), dist)
        if hit is not None:
            if self.max_bounces <= 0:
                self.pos = hit.point
                return "detonate"
            self.max_bounces -= 1
            # 反彈：反射法線分量，保留切線分量
            vn = self.vel.dot(hit.normal)
            if vn < 0.0:
                self.vel = self.vel - hit.normal * (1.0 + self.bounce_restitution) * vn
            self.pos = hit.point + hit.normal * 0.05
            return "wall_bounce"
        # 地面（y=0 平面）碰撞
        if new_pos.y <= 0.0 and self.vel.y < 0.0:
            if self.max_bounces <= 0:
                self.pos = Vec3(new_pos.x, 0.0, new_pos.z)
                return "detonate"
            self.max_bounces -= 1
            self.vel = Vec3(self.vel.x, -self.vel.y * self.bounce_restitution, self.vel.z)
            self.pos = Vec3(new_pos.x, 0.05, new_pos.z)
            return "wall_bounce"
        self.pos = new_pos
        if self.pos.y < map_data.bounds_min.y - 5.0:
            return "detonate"
        return None


def explode(
    world,
    map_data: MapData,
    center: Vec3,
    radius: float,
    damage: float,
    team: int,
    ignore_los: bool = False,
    source_slot: int = -1,
    weapon_key: str = "explosion",
    flat: bool = False,
) -> list[int]:
    """範圍傷害：半徑內線性衰減（flat=True 時範圍內全傷）；
    LOS 阻擋時減半（除非 ignore_los）。"""
    victims: list[int] = []
    for slot, p in enumerate(world.players):
        if not p.alive or p.team == team:
            continue
        dist = p.pos.distance_to(center)
        if dist > radius:
            continue
        if flat:
            dmg = damage
        else:
            dmg = damage * (1.0 - dist / radius)
        if not ignore_los:
            if not map_data.los_clear(center, p.pos + Vec3(0, 1.0, 0)):
                dmg *= 0.5
        if dmg > 0:
            p.apply_damage(dmg, source_slot=source_slot, weapon_key=weapon_key)
            victims.append(slot)
    return victims
