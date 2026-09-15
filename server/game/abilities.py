"""
server/game/abilities.py — M10-12/M15 技能框架 + 10 名特務專屬技能
===================================================================
IAbility 抽象介面 + 技能原型：
  * ProjectileAbility   投擲物物理（閃光/碎片手榴彈，反彈+拋物線）
  * SmokeAbility        視野遮蔽（球形/不規則 LOS 阻斷器 + 持續時間控制）
  * DeployableAbility   地圖部署物（牆面/地面觸發型陷阱）
  * LineProjectile      線性投射物（Sova Shock Bolt / Jett Knives）
  * WallDeployable       牆壁/屏障部署物（Sage Wall / Viper Screen）
  * ZoneDetector        區域偵測器（Sova Recon / Cypher Cam）
  * TeleportAbility     傳送技能（Omen / Yoru）

10 名核心特務（每名 C/Q/E/X 四技能）：
  決鬥者：捷提 Jett / 夜露 Yoru / 霓虹 Neon
  偵查者：蘇法 Sova / 布雷奇 Breach / 凱歐 KAY/O
  控場者：幽影 Omen / 布里姆 Brimstone / 薇勞 Viper
  哨衛  ：賢者 Sage
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from server.core.math_core import Vec3
from server.game.ballistics import Projectile, explode
from server.game.mapdata import SmokeCloud
from server.game.status import (
    BLIND, CONCUSS, VULNERABLE, SPEED_BOOST,
    NEARSIGHT, SUPPRESSED, DECAY, SLOW, DEAFENED, REVEALED,
)


class IAbility(ABC):
    name: str = "ability"
    charges: int = 1
    cooldown: float = 0.0

    @abstractmethod
    def cast(self, world, caster_slot: int, aim_dir: Vec3) -> None:
        ...

    def update(self, dt: float, world) -> None:  # 可選：持續效果更新
        pass


# ====================================================================== #
# 基礎技能原型（原有，供人物產生器使用）
# ====================================================================== #

@dataclass(slots=True)
class FlashAbility(IAbility):
    """閃光彈：拋物線投出，落地/撞牆即爆或 1.2s 後自爆 → 範圍內敵方閃瞎。"""
    name: str = "flash"
    charges: int = 1
    cooldown: float = 20.0
    throw_speed: float = 16.0
    blind_radius: float = 8.0
    blind_duration: float = 2.0
    fuse: float = 1.2

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        vel = aim_dir * self.throw_speed + Vec3(0, 2.5, 0)
        world.spawn_projectile(
            Projectile(origin, vel, p.team, behavior="flash", fuse_time=self.fuse,
                       max_bounces=0,
                       owner_slot=caster_slot, params={"radius": self.blind_radius,
                                                       "duration": self.blind_duration})
        )


@dataclass(slots=True)
class FragAbility(IAbility):
    """碎片手榴彈：反彈物理 + 1.5s 引信 → 爆炸範圍傷害。"""
    name: str = "frag"
    charges: int = 1
    cooldown: float = 25.0
    throw_speed: float = 15.0
    damage: float = 90.0
    radius: float = 15.0
    fuse: float = 1.5

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        vel = aim_dir * self.throw_speed + Vec3(0, 1.0, 0)
        world.spawn_projectile(
            Projectile(origin, vel, p.team, behavior="frag", fuse_time=self.fuse,
                       damage=self.damage, explosion_radius=self.radius,
                       owner_slot=caster_slot)
        )


@dataclass(slots=True)
class SmokeAbility(IAbility):
    """煙霧彈：拋物線投出，落地生成球形 LOS 阻斷器。"""
    name: str = "smoke"
    charges: int = 2
    cooldown: float = 10.0
    throw_speed: float = 15.0
    smoke_radius: float = 3.5
    duration: float = 15.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        vel = aim_dir * self.throw_speed + Vec3(0, 1.0, 0)
        world.spawn_projectile(
            Projectile(origin, vel, p.team, behavior="smoke", owner_slot=caster_slot,
                       params={"radius": self.smoke_radius, "duration": self.duration})
        )


class TrapDeployable:
    """牆面/地面觸發型陷阱：單次觸發，命中敵方造成傷害 + 暈眩。"""

    def __init__(self, pos: Vec3, team: int, radius: float = 3.0, lifetime: float = 30.0,
                 damage: float = 60.0, concuss_duration: float = 2.0):
        self.pos = pos
        self.team = team
        self.radius = radius
        self.time_left = lifetime
        self.damage = damage
        self.concuss_duration = concuss_duration
        self.triggered = False

    def update(self, dt: float, world) -> bool:
        self.time_left -= dt
        if self.time_left <= 0.0 or self.triggered:
            return True
        for slot, p in enumerate(world.players):
            if not p.alive or p.team == self.team:
                continue
            if p.pos.distance_to(self.pos) <= self.radius:
                self.triggered = True
                p.apply_damage(self.damage, source_slot=-1, weapon_key="trap")
                p.status.apply(CONCUSS, self.concuss_duration, 1.0)
                return True
        return False


@dataclass(slots=True)
class DeployableAbility(IAbility):
    """放置型陷阱：沿瞄準方向 raycast 放置於最近表面。"""
    name: str = "trap"
    charges: int = 1
    cooldown: float = 20.0
    trigger_radius: float = 3.0
    damage: float = 60.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.4, 0)
        hit = world.map_data.raycast(origin, aim_dir, 8.0)
        pos = hit.point + hit.normal * 0.1 if hit is not None else p.pos + aim_dir * 2.0
        world.deployables.append(
            TrapDeployable(pos, p.team, radius=self.trigger_radius, damage=self.damage)
        )


@dataclass(slots=True)
class StimAbility(IAbility):
    """戰鬥刺激：自身移動加速，持續 duration 秒。"""
    name: str = "stim"
    charges: int = 1
    cooldown: float = 14.0
    duration: float = 6.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        p.status.apply(SPEED_BOOST, self.duration, 1.0)


@dataclass(slots=True)
class HealAbility(IAbility):
    """自我治療：恢復 amount 點生命。"""
    name: str = "heal"
    charges: int = 1
    cooldown: float = 20.0
    amount: float = 50.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        p.health = min(100.0, p.health + self.amount)


# ====================================================================== #
# 新增技能原型
# ====================================================================== #

@dataclass(slots=True)
class LineProjectileAbility(IAbility):
    """線性投射物：直線飛行、命中敵人造成傷害（Jett 飛刀 / Sova Shock Bolt）。"""
    name: str = "line_proj"
    charges: int = 1
    cooldown: float = 10.0
    speed: float = 30.0
    damage: float = 50.0
    lifetime: float = 2.0
    radius: float = 0.5

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        # 線性投射物：gravity=0，直線飛行
        proj = Projectile(
            origin, aim_dir * self.speed, p.team,
            gravity=0.0, bounce_restitution=0.0, max_bounces=0,
            fuse_time=self.lifetime, damage=self.damage,
            explosion_radius=self.radius, behavior="line_hit",
            owner_slot=caster_slot,
            params={"radius": self.radius, "damage": self.damage},
        )
        world.spawn_projectile(proj)


@dataclass(slots=True)
class WallDeployAbility(IAbility):
    """牆壁/屏障部署物：在指定位置生成牆壁（Sage 冰牆 / Viper 毒幕）。"""
    name: str = "wall"
    charges: int = 1
    cooldown: float = 30.0
    wall_length: float = 6.0
    wall_height: float = 3.0
    wall_thickness: float = 0.5
    duration: float = 15.0
    wall_kind: str = "solid"  # "solid" = 阻擋視線+移動, "toxic" = 阻擋視線+扣血

    def cast(self, world, caster_slot, aim_dir):
        from server.game.mapdata import Wall
        p = world.players[caster_slot]
        # 牆壁沿瞄準方向垂直放置
        center = p.pos + aim_dir * 2.0
        perp = Vec3(-aim_dir.z, 0, aim_dir.x).normalized() if aim_dir.horizontal().length_sq() > 0.01 else Vec3(1, 0, 0)
        mn = center - perp * (self.wall_length * 0.5) + Vec3(0, 0, 0)
        mx = center + perp * (self.wall_length * 0.5) + Vec3(0, self.wall_height, 0)
        # 加入牆面列表（臨時牆，到期後移除）
        temp_wall = Wall(
            Vec3(min(mn.x, mx.x), 0, min(mn.z, mx.z)),
            Vec3(max(mn.x, mx.x), self.wall_height, max(mn.z, mx.z)),
            "concrete" if self.wall_kind == "solid" else "wood",
        )
        world.map_data.walls.append(temp_wall)
        world.map_data._ray_hash = None  # 清除空間雜湊快取
        # 設定計時器移除（透過 deployables 機制）
        wall_entity = _TimedWall(temp_wall, world.map_data, self.duration, self.wall_kind, p.team)
        world.deployables.append(wall_entity)


class _TimedWall:
    """臨時牆壁：到期後從地圖移除；toxic 類型每 tick 對牆內敵人扣血。"""

    def __init__(self, wall, map_data, duration: float, kind: str, team: int):
        self.wall = wall
        self.map_data = map_data
        self.time_left = duration
        self.kind = kind
        self.team = team
        self.triggered = False

    def update(self, dt: float, world) -> bool:
        self.time_left -= dt
        # toxic 牆：每 tick 對牆內敵人施加 Decay
        if self.kind == "toxic" and self.time_left > 0:
            center = Vec3(
                (self.wall.mn.x + self.wall.mx.x) * 0.5,
                1.0,
                (self.wall.mn.z + self.wall.mx.z) * 0.5,
            )
            w = self.wall.mx.x - self.wall.mn.x
            d = self.wall.mx.z - self.wall.mn.z
            radius = max(w, d) * 0.5 + 0.5
            for p in world.players:
                if p.alive and p.team != self.team:
                    if p.pos.distance_to(center) <= radius:
                        p.status.apply(DECAY, 0.5, 8.0)  # 8 dmg/s, 0.5s 刷新
        if self.time_left <= 0.0:
            # 移除牆面
            if self.wall in self.map_data.walls:
                self.map_data.walls.remove(self.wall)
                self.map_data._ray_hash = None
            return True
        return False


@dataclass(slots=True)
class SlowOrbAbility(IAbility):
    """減速球：投出後在落地點生成減速區域（Sage Slow Orb）。"""
    name: str = "slow_orb"
    charges: int = 1
    cooldown: float = 15.0
    throw_speed: float = 14.0
    slow_radius: float = 4.0
    slow_duration: float = 5.0
    slow_potency: float = 1.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        vel = aim_dir * self.throw_speed + Vec3(0, 2.0, 0)
        world.spawn_projectile(
            Projectile(origin, vel, p.team, behavior="slow_orb",
                       owner_slot=caster_slot,
                       params={"radius": self.slow_radius,
                               "duration": self.slow_duration,
                               "potency": self.slow_potency})
        )


@dataclass(slots=True)
class TeleportAbility(IAbility):
    """傳送：將施法者傳送到瞄準方向前方的位置（Omen Shrouded Step / Yoru Gatecrash）。"""
    name: str = "teleport"
    charges: int = 1
    cooldown: float = 25.0
    teleport_dist: float = 6.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        target = p.pos + aim_dir * self.teleport_dist
        target = Vec3(target.x, p.pos.y, target.z)
        # raycast 確認目標位置無牆壁阻擋
        hit = world.map_data.raycast(p.pos + Vec3(0, 0.5, 0), aim_dir, self.teleport_dist)
        if hit is not None:
            target = hit.point - aim_dir * 0.5
        p.pos = target
        p.vel = Vec3()
        world.event_log.append(f"teleport: slot{caster_slot} -> {target}")


@dataclass(slots=True)
class NearsightLineAbility(IAbility):
    """直線近視彈：沿瞄準方向發射，命中敵方施加近視+聽覺封鎖（Omen Paranoia / Breach Flash）。"""
    name: str = "nearsight"
    charges: int = 1
    cooldown: float = 22.0
    speed: float = 25.0
    nearsight_duration: float = 3.0
    deafen_duration: float = 1.5
    radius: float = 3.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.speed, p.team,
                       gravity=0.0, bounce_restitution=0.0, max_bounces=0,
                       fuse_time=1.5, behavior="nearsight",
                       owner_slot=caster_slot,
                       params={"radius": self.radius,
                               "ns_duration": self.nearsight_duration,
                               "deafen_duration": self.deafen_duration})
        )


@dataclass(slots=True)
class SuppressionFieldAbility(IAbility):
    """範圍技能封鎖：在施法者周圍生成封鎖區域，區域內敵方被技能封鎖（KAY/O ZERO/point）。"""
    name: str = "suppress"
    charges: int = 1
    cooldown: float = 20.0
    radius: float = 8.0
    suppress_duration: float = 3.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.0, 0)
        # 線性投射 → 落地後展開封鎖範圍
        world.spawn_projectile(
            Projectile(origin, aim_dir * 18.0, p.team,
                       gravity=0.0, max_bounces=0, fuse_time=0.4,
                       behavior="suppress",
                       owner_slot=caster_slot,
                       params={"radius": self.radius,
                               "duration": self.suppress_duration})
        )


@dataclass(slots=True)
class BeamUltimateAbility(IAbility):
    """線性穿透光束終極技能：沿瞄準方向發射穿透牆壁的光束（Sova Hunter's Fury / Breach Rolling Earthquake）。"""
    name: str = "beam_ult"
    charges: int = 3  # 終極技能充能
    cooldown: float = 0.0  # 終極技能用充能而非冷卻
    damage: float = 80.0
    beam_length: float = 50.0
    beam_radius: float = 1.5

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0)
        end = origin + aim_dir * self.beam_length
        # 光束沿途對所有敵方造成傷害（穿透牆壁）
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            # 計算目標到光束的距離
            target_pos = target.pos + Vec3(0, 1.0, 0)
            ab = end - origin
            t = max(0.0, min(1.0, (target_pos - origin).dot(ab) / ab.length_sq()))
            closest = origin + ab * t
            if target_pos.distance_to(closest) <= self.beam_radius:
                target.apply_damage(self.damage, source_slot=caster_slot, weapon_key="beam_ult")
                target.status.apply(CONCUSS, 1.5, 1.0)
        world.event_log.append(f"beam_ult: slot{caster_slot} fired")


@dataclass(slots=True)
class ThrownKnifeAbility(IAbility):
    """投擲飛刀終極技能：投出多把飛刀，每把造成傷害（Jett Blade Storm）。"""
    name: str = "blade_storm"
    charges: int = 1
    cooldown: float = 0.0  # 終極技能
    knife_count: int = 5
    knife_damage: float = 50.0
    throw_speed: float = 35.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        # 發射 5 把飛刀，略微散開
        for i in range(self.knife_count):
            offset_angle = (i - 2) * 2.0  # 度
            import math
            rad = math.radians(offset_angle)
            # 在水平面上偏轉
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            dir_v = Vec3(
                aim_dir.x * cos_a - aim_dir.z * sin_a,
                aim_dir.y,
                aim_dir.x * sin_a + aim_dir.z * cos_a,
            )
            world.spawn_projectile(
                Projectile(origin, dir_v * self.throw_speed, p.team,
                           gravity=0.0, bounce_restitution=0.0, max_bounces=0,
                           fuse_time=1.5, damage=self.knife_damage,
                           explosion_radius=0.6, behavior="line_hit",
                           owner_slot=caster_slot,
                           params={"radius": 0.6, "damage": self.knife_damage})
            )


@dataclass(slots=True)
class FlameWallAbility(IAbility):
    """火焰牆：沿地面生成火焰區域，阻擋視線並造成持續傷害（Brimstone Incendiary / Phoenix Blaze）。"""
    name: str = "flame_wall"
    charges: int = 1
    cooldown: float = 25.0
    radius: float = 3.0
    damage: float = 40.0
    duration: float = 6.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * 15.0, p.team,
                       gravity=0.0, max_bounces=0, fuse_time=0.3,
                       behavior="flame",
                       owner_slot=caster_slot,
                       params={"radius": self.radius, "damage": self.damage,
                               "duration": self.duration})
        )


@dataclass(slots=True)
class OrbitalStrikeAbility(IAbility):
    """軌道打擊終極技能：在指定區域延遲後造成範圍致死傷害（Brimstone Orbital Strike）。"""
    name: str = "orbital_strike"
    charges: int = 1
    cooldown: float = 0.0
    radius: float = 5.0
    damage: float = 150.0
    delay: float = 2.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 在瞄準方向的地面落點展開打擊
        origin = p.pos + Vec3(0, 1.5, 0)
        hit = world.map_data.raycast(origin, aim_dir, 30.0)
        target_pos = hit.point if hit is not None else p.pos + aim_dir * 10.0
        # 用 deployable 機制延遲爆炸
        strike = _DelayedStrike(target_pos, p.team, self.radius, self.damage, self.delay)
        world.deployables.append(strike)


class _DelayedStrike:
    """延遲範圍爆炸（Brimstone Orbital Strike / Raze Showstopper）。"""

    def __init__(self, pos: Vec3, team: int, radius: float, damage: float, delay: float):
        self.pos = pos
        self.team = team
        self.radius = radius
        self.damage = damage
        self.time_left = delay
        self.triggered = False

    def update(self, dt: float, world) -> bool:
        self.time_left -= dt
        if self.time_left <= 0.0 and not self.triggered:
            self.triggered = True
            explode(world, world.map_data, self.pos, self.radius, self.damage,
                    team=self.team, ignore_los=True, source_slot=-1,
                    weapon_key="orbital_strike", flat=True)
            return True
        return False


@dataclass(slots=True)
class RocketUltimateAbility(IAbility):
    """火箭筒終極技能：發射一枚火箭彈，命中後範圍爆炸（Raze Showstopper）。"""
    name: str = "rocket_ult"
    charges: int = 1
    cooldown: float = 0.0
    speed: float = 25.0
    damage: float = 120.0
    radius: float = 4.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.speed, p.team,
                       gravity=2.0, max_bounces=0, fuse_time=3.0,
                       damage=self.damage, explosion_radius=self.radius,
                       behavior="frag", owner_slot=caster_slot)
        )


@dataclass(slots=True)
class SprintAbility(IAbility):
    """衝刺技能：瞬間加速向前（Neon Sprint / Jett Tailwind）。"""
    name: str = "sprint"
    charges: int = 2
    cooldown: float = 8.0
    speed_mult: float = 2.0
    duration: float = 1.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        p.status.apply(SPEED_BOOST, self.duration, self.speed_mult - 1.0)
        # 給予一個瞬間速度衝量
        impulse = aim_dir * 8.0
        p.vel = p.vel + impulse


@dataclass(slots=True)
class ElectricWallAbility(IAbility):
    """電牆：沿前方生成電牆，阻擋視線並使穿越者減速（Neon Fast Lane）。"""
    name: str = "electric_wall"
    charges: int = 1
    cooldown: float = 18.0
    wall_length: float = 8.0
    duration: float = 7.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 在前方放置一堵電牆
        from server.game.mapdata import Wall
        center = p.pos + aim_dir * 3.0
        perp = Vec3(-aim_dir.z, 0, aim_dir.x)
        if perp.length_sq() > 0.01:
            perp = perp.normalized()
        mn = Vec3(
            center.x - perp.x * self.wall_length * 0.5,
            0,
            center.z - perp.z * self.wall_length * 0.5,
        )
        mx = Vec3(
            center.x + perp.x * self.wall_length * 0.5,
            2.5,
            center.z + perp.z * self.wall_length * 0.5,
        )
        temp_wall = Wall(mn, mx, "wood")
        world.map_data.walls.append(temp_wall)
        world.map_data._ray_hash = None
        wall_entity = _TimedWall(temp_wall, world.map_data, self.duration, "toxic", p.team)
        world.deployables.append(wall_entity)


@dataclass(slots=True)
class ElectricBeamUltAbility(IAbility):
    """閃電光束終極技能：沿前方發射閃電光束，持續傷害（Neon Overdrive）。"""
    name: str = "lightning_ult"
    charges: int = 1
    cooldown: float = 0.0
    damage: float = 30.0
    beam_length: float = 15.0
    beam_radius: float = 1.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0)
        end = origin + aim_dir * self.beam_length
        # 線性穿透閃電
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            target_pos = target.pos + Vec3(0, 1.0, 0)
            ab = end - origin
            t = max(0.0, min(1.0, (target_pos - origin).dot(ab) / ab.length_sq()))
            closest = origin + ab * t
            if target_pos.distance_to(closest) <= self.beam_radius:
                target.apply_damage(self.damage, source_slot=caster_slot, weapon_key="lightning_ult")
                target.status.apply(SLOW, 2.0, 1.0)
        world.event_log.append(f"lightning_ult: slot{caster_slot} fired")


@dataclass(slots=True)
class InvisibilityAbility(IAbility):
    """隱形傳送：短暫隱形 + 傳送到前方位置（Yoru Dimensional Drift 終極）。"""
    name: str = "invis_teleport"
    charges: int = 1
    cooldown: float = 0.0
    duration: float = 8.0
    teleport_dist: float = 8.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 速度加速 + 隱形效果（近視施於自身 = 不被遠方敵人看見）
        p.status.apply(SPEED_BOOST, self.duration, 0.5)
        # 傳送到前方
        target = p.pos + aim_dir * self.teleport_dist
        hit = world.map_data.raycast(p.pos + Vec3(0, 0.5, 0), aim_dir, self.teleport_dist)
        if hit is not None:
            target = hit.point - aim_dir * 0.5
        p.pos = Vec3(target.x, p.pos.y, target.z)
        p.vel = Vec3()
        world.event_log.append(f"invis_teleport: slot{caster_slot}")


@dataclass(slots=True)
class FakeFootstepAbility(IAbility):
    """假腳步聲：在指定位置生成腳步聲誘餌（Yoru Fakeout）。"""
    name: str = "fake_footstep"
    charges: int = 1
    cooldown: float = 15.0
    duration: float = 4.0
    radius: float = 5.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        # 投出一個假的腳步聲源
        world.spawn_projectile(
            Projectile(origin, aim_dir * 12.0, p.team,
                       gravity=0.0, max_bounces=1, fuse_time=self.duration,
                       behavior="fake_footstep",
                       owner_slot=caster_slot,
                       params={"duration": self.duration})
        )


@dataclass(slots=True)
class ReconBoltAbility(IAbility):
    """偵查箭：投出後在命中點展開偵測範圍，範圍內敵方被 REVEALED（Sova Recon Bolt）。"""
    name: str = "recon_bolt"
    charges: int = 1
    cooldown: float = 15.0
    speed: float = 20.0
    reveal_radius: float = 6.0
    reveal_duration: float = 2.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.speed, p.team,
                       gravity=5.0, max_bounces=2, fuse_time=2.0,
                       behavior="recon",
                       owner_slot=caster_slot,
                       params={"radius": self.reveal_radius,
                               "duration": self.reveal_duration})
        )


@dataclass(slots=True)
class OwlDroneAbility(IAbility):
    """貓頭鷹無人機：投射一架無人機，沿瞄準方向飛行並標記敵方（Sova Owl Drone）。"""
    name: str = "owl_drone"
    charges: int = 1
    cooldown: float = 20.0
    speed: float = 18.0
    duration: float = 3.0
    reveal_radius: float = 4.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.speed, p.team,
                       gravity=0.0, max_bounces=0, fuse_time=self.duration,
                       behavior="drone",
                       owner_slot=caster_slot,
                       params={"radius": self.reveal_radius,
                               "duration": self.reveal_duration})
        )


@dataclass(slots=True)
class HealingOrbAbility(IAbility):
    """治療球：對自身或範圍內友方恢復生命（Sage Healing Orb）。"""
    name: str = "heal_orb"
    charges: int = 1
    cooldown: float = 15.0
    heal_amount: float = 60.0
    heal_duration: float = 3.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 自身治療（漸進式）
        p.health = min(100.0, p.health + self.heal_amount)
        world.event_log.append(f"heal_orb: slot{caster_slot} +{self.heal_amount}hp")


@dataclass(slots=True)
class BarrierWallAbility(IAbility):
    """冰牆終極：在瞄準方向升起一道牆壁，阻擋視線和移動（Sage Barrier Orb）。"""
    name: str = "barrier_wall"
    charges: int = 1
    cooldown: float = 30.0
    wall_length: float = 5.0
    wall_height: float = 3.5
    duration: float = 15.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        from server.game.mapdata import Wall
        center = p.pos + aim_dir * 2.5
        perp = Vec3(-aim_dir.z, 0, aim_dir.x)
        if perp.length_sq() > 0.01:
            perp = perp.normalized()
        mn = Vec3(
            center.x - perp.x * self.wall_length * 0.5,
            0,
            center.z - perp.z * self.wall_length * 0.5,
        )
        mx = Vec3(
            center.x + perp.x * self.wall_length * 0.5,
            self.wall_height,
            center.z + perp.z * self.wall_length * 0.5,
        )
        temp_wall = Wall(mn, mx, "concrete")
        world.map_data.walls.append(temp_wall)
        world.map_data._ray_hash = None
        wall_entity = _TimedWall(temp_wall, world.map_data, self.duration, "solid", p.team)
        world.deployables.append(wall_entity)


@dataclass(slots=True)
class ResurrectionAbility(IAbility):
    """復活終極技能：復活一名已死亡的隊友至施法者旁（Sage Resurrection）。"""
    name: str = "resurrection"
    charges: int = 1
    cooldown: float = 0.0

    def cast(self, world, caster_slot, aim_dir):
        caster = world.players[caster_slot]
        # 尋找最近的一名已死亡同隊友方
        best_slot = -1
        best_dist = 999.0
        for slot, p in enumerate(world.players):
            if not p.alive and p.team == caster.team:
                d = p.pos.distance_to(caster.pos)
                if d < best_dist:
                    best_dist = d
                    best_slot = slot
        if best_slot >= 0:
            target = world.players[best_slot]
            target.alive = True
            target.health = 100.0
            target.shield_hp = 0.0
            target.pos = caster.pos + aim_dir * 1.0
            target.vel = Vec3()
            world.event_log.append(f"resurrection: slot{caster_slot} -> slot{best_slot}")


@dataclass(slots=True)
class ToxicScreenAbility(IAbility):
    """毒幕終極：沿前方生成長條毒牆，穿越者持續扣血（Viper Toxic Screen）。"""
    name: str = "toxic_screen"
    charges: int = 1
    cooldown: float = 12.0
    wall_length: float = 12.0
    duration: float = 10.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        from server.game.mapdata import Wall
        center = p.pos + aim_dir * 4.0
        perp = Vec3(-aim_dir.z, 0, aim_dir.x)
        if perp.length_sq() > 0.01:
            perp = perp.normalized()
        mn = Vec3(
            center.x - perp.x * self.wall_length * 0.5,
            0,
            center.z - perp.z * self.wall_length * 0.5,
        )
        mx = Vec3(
            center.x + perp.x * self.wall_length * 0.5,
            2.0,
            center.z + perp.z * self.wall_length * 0.5,
        )
        temp_wall = Wall(mn, mx, "wood")
        world.map_data.walls.append(temp_wall)
        world.map_data._ray_hash = None
        wall_entity = _TimedWall(temp_wall, world.map_data, self.duration, "toxic", p.team)
        world.deployables.append(wall_entity)


@dataclass(slots=True)
class ViperPitAbility(IAbility):
    """毒蛇之穴終極：在施法者周圍生成大範圍毒霧區域（Viper Viper's Pit）。"""
    name: str = "viper_pit"
    charges: int = 1
    cooldown: float = 0.0
    radius: float = 8.0
    duration: float = 12.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 生成大範圍煙霧 + 持續 decay
        cloud = SmokeCloud(p.pos, self.radius, self.duration, world.rng)
        world.smokes.append(cloud)
        # 在範圍內對敵方施加 Decay
        for slot, target in enumerate(world.players):
            if target.alive and target.team != p.team:
                if target.pos.distance_to(p.pos) <= self.radius:
                    target.status.apply(DECAY, self.duration, 10.0)
        world.event_log.append(f"viper_pit: slot{caster_slot}")


@dataclass(slots=True)
class IncendiaryAbility(IAbility):
    """燃燒彈：投出後在落地點生成火焰區域，持續扣血（Brimstone Incendiary）。"""
    name: str = "incendiary"
    charges: int = 1
    cooldown: float = 20.0
    throw_speed: float = 14.0
    radius: float = 3.0
    damage: float = 40.0
    duration: float = 6.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.throw_speed, p.team,
                       behavior="flame", max_bounces=1, fuse_time=0.5,
                       owner_slot=caster_slot,
                       params={"radius": self.radius, "damage": self.damage,
                               "duration": self.duration})
        )


@dataclass(slots=True)
class StimBeaconAbility(IAbility):
    """刺激信標：在地面放置信標，範圍內友方獲得加速（Brimstone Stim Beacon）。"""
    name: str = "stim_beacon"
    charges: int = 1
    cooldown: float = 15.0
    radius: float = 4.0
    duration: float = 8.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        beacon = _StimBeacon(p.pos, p.team, self.radius, self.duration)
        world.deployables.append(beacon)


class _StimBeacon:
    """刺激信標部署物：範圍內友方持續獲得加速。"""

    def __init__(self, pos: Vec3, team: int, radius: float, duration: float):
        self.pos = pos
        self.team = team
        self.radius = radius
        self.time_left = duration
        self.triggered = False

    def update(self, dt: float, world) -> bool:
        self.time_left -= dt
        if self.time_left <= 0.0:
            return True
        for p in world.players:
            if p.alive and p.team == self.team:
                if p.pos.distance_to(self.pos) <= self.radius:
                    p.status.apply(SPEED_BOOST, 0.3, 0.3)
        return False


@dataclass(slots=True)
class SkySmokeAbility(IAbility):
    """空投煙霧：在瞄準方向遠處投放煙霧（Brimstone Sky Smoke）。"""
    name: str = "sky_smoke"
    charges: int = 2
    cooldown: float = 12.0
    smoke_radius: float = 3.5
    duration: float = 14.0
    throw_dist: float = 15.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        # 在瞄準方向的指定距離生成煙霧
        target = p.pos + aim_dir * self.throw_dist
        target = Vec3(target.x, 0, target.z)
        cloud = SmokeCloud(target, self.smoke_radius, self.duration, world.rng)
        world.smokes.append(cloud)


@dataclass(slots=True)
class EarthquakeAbility(IAbility):
    """地震終極技能：沿前方扇形區域造成範圍暈眩+傷害，穿透牆壁（Breach Rolling Earthquake）。"""
    name: str = "earthquake"
    charges: int = 1
    cooldown: float = 0.0
    damage: float = 50.0
    cone_length: float = 20.0
    cone_half_angle: float = 30.0  # 度
    stun_duration: float = 3.0

    def cast(self, world, caster_slot, aim_dir):
        import math
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.0, 0)
        cos_half = math.cos(math.radians(self.cone_half_angle))
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            to_target = target.pos - origin
            dist = to_target.length()
            if dist > self.cone_length:
                continue
            to_target_dir = to_target.normalized()
            if aim_dir.dot(to_target_dir) >= cos_half:
                target.apply_damage(self.damage, source_slot=caster_slot, weapon_key="earthquake")
                target.status.apply(CONCUSS, self.stun_duration, 1.0)
        world.event_log.append(f"earthquake: slot{caster_slot}")


@dataclass(slots=True)
class FaultLineAbility(IAbility):
    """斷層：沿瞄準方向發射地震波，命中敵方造成暈眩（Breach Fault Line）。"""
    name: str = "fault_line"
    charges: int = 1
    cooldown: float = 18.0
    stun_duration: float = 2.5
    range: float = 15.0
    radius: float = 2.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.0, 0)
        end = origin + aim_dir * self.range
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            target_pos = target.pos + Vec3(0, 1.0, 0)
            ab = end - origin
            t = max(0.0, min(1.0, (target_pos - origin).dot(ab) / ab.length_sq()))
            closest = origin + ab * t
            if target_pos.distance_to(closest) <= self.radius:
                target.apply_damage(30.0, source_slot=caster_slot, weapon_key="fault_line")
                target.status.apply(CONCUSS, self.stun_duration, 1.0)
        world.event_log.append(f"fault_line: slot{caster_slot}")


@dataclass(slots=True)
class AftershockAbility(IAbility):
    """餘震：穿牆爆炸，對牆後敵方造成範圍傷害（Breach Aftershock — C 技能近似）。"""
    name: str = "aftershock"
    charges: int = 1
    cooldown: float = 20.0
    damage: float = 60.0
    range: float = 8.0
    radius: float = 2.5

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.0, 0)
        end = origin + aim_dir * self.range
        # 穿牆命中
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            target_pos = target.pos + Vec3(0, 1.0, 0)
            ab = end - origin
            t = max(0.0, min(1.0, (target_pos - origin).dot(ab) / ab.length_sq()))
            closest = origin + ab * t
            if target_pos.distance_to(closest) <= self.radius:
                target.apply_damage(self.damage, source_slot=caster_slot, weapon_key="aftershock")
        world.event_log.append(f"aftershock: slot{caster_slot}")


@dataclass(slots=True)
class NULLCmdAbility(IAbility):
    """NULL/cmd 終極：大範圍技能封鎖，持續時間內敵方無法使用技能（KAY/O NULL/cmd）。"""
    name: str = "null_cmd"
    charges: int = 1
    cooldown: float = 0.0
    radius: float = 12.0
    duration: float = 6.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            if target.pos.distance_to(p.pos) <= self.radius:
                target.status.apply(SUPPRESSED, self.duration, 1.0)
        world.event_log.append(f"null_cmd: slot{caster_slot}")


@dataclass(slots=True)
class FlashpointAbility(IAbility):
    """閃點：蓄力後沿牆壁反彈的閃光彈（Breach Flashpoint — C 技能近似）。"""
    name: str = "flashpoint"
    charges: int = 1
    cooldown: float = 25.0
    throw_speed: float = 14.0
    blind_duration: float = 3.0
    blind_radius: float = 6.0
    fuse: float = 1.0

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
        world.spawn_projectile(
            Projectile(origin, aim_dir * self.throw_speed, p.team,
                       behavior="flash", fuse_time=self.fuse, max_bounces=2,
                       owner_slot=caster_slot,
                       params={"radius": self.blind_radius, "duration": self.blind_duration})
        )


@dataclass(slots=True)
class HunterFuryAbility(IAbility):
    """獵手之怒終極：連續三道穿透光束（Sova Hunter's Fury）。"""
    name: str = "hunter_fury"
    charges: int = 3
    cooldown: float = 0.0
    damage: float = 80.0
    beam_length: float = 50.0
    beam_radius: float = 1.5

    def cast(self, world, caster_slot, aim_dir):
        p = world.players[caster_slot]
        origin = p.pos + Vec3(0, 1.5, 0)
        end = origin + aim_dir * self.beam_length
        for slot, target in enumerate(world.players):
            if not target.alive or target.team == p.team:
                continue
            target_pos = target.pos + Vec3(0, 1.0, 0)
            ab = end - origin
            t = max(0.0, min(1.0, (target_pos - origin).dot(ab) / ab.length_sq()))
            closest = origin + ab * t
            if target_pos.distance_to(closest) <= self.beam_radius:
                target.apply_damage(self.damage, source_slot=caster_slot, weapon_key="hunter_fury")
        world.event_log.append(f"hunter_fury: slot{caster_slot}")


# ====================================================================== #
# 技能工廠（人物產生器共用）
# ====================================================================== #

ABILITY_FACTORY: dict[str, type] = {
    "flash": FlashAbility,
    "frag": FragAbility,
    "smoke": SmokeAbility,
    "trap": DeployableAbility,
    "stim": StimAbility,
    "heal": HealAbility,
}


def build_ability(name: str) -> IAbility:
    if name not in ABILITY_FACTORY:
        raise KeyError(f"unknown ability: {name}")
    return ABILITY_FACTORY[name]()


# ====================================================================== #
# 能力槽與特務定義
# ====================================================================== #

@dataclass(slots=True)
class AbilitySlot:
    ability: IAbility
    charges_left: int
    cooldown_left: float = 0.0

    def can_cast(self) -> bool:
        return self.charges_left > 0 and self.cooldown_left <= 0.0

    def cast(self, world, caster_slot, aim_dir) -> bool:
        if not self.can_cast():
            return False
        self.ability.cast(world, caster_slot, aim_dir)
        self.charges_left -= 1
        self.cooldown_left = self.ability.cooldown
        return True

    def update(self, dt: float) -> None:
        if self.cooldown_left > 0:
            self.cooldown_left = max(0.0, self.cooldown_left - dt)


class AbilitySystem:
    """每位玩家的技能槽集合（charges/cooldown 由伺服器權威管理）。"""

    def __init__(self, defs: list[IAbility]):
        self.slots = [AbilitySlot(d, d.charges) for d in defs]

    def cast(self, index: int, world, caster_slot: int, aim_dir: Vec3) -> bool:
        if not (0 <= index < len(self.slots)):
            return False
        # 技能封鎖檢查（KAY/O suppression）
        if not world.players[caster_slot].status.can_use_ability:
            return False
        return self.slots[index].cast(world, caster_slot, aim_dir)

    def update(self, dt: float) -> None:
        for s in self.slots:
            s.update(dt)

    def refill(self) -> None:
        """補滿所有充能並清除冷卻（Spike Rush 每回合免費技能）。"""
        for s in self.slots:
            s.charges_left = s.ability.charges
            s.cooldown_left = 0.0

    def snapshot(self) -> list[dict]:
        return [
            {"name": s.ability.name, "charges": s.charges_left, "cooldown": s.cooldown_left}
            for s in self.slots
        ]


# ====================================================================== #
# 特務專屬技能類別
# ====================================================================== #

@dataclass(slots=True)
class CloudburstAbility(IAbility):
	"""煙雲：投出小型煙霧球，落地後快速展開（Jett Cloudburst）。"""
	name: str = "cloudburst"
	charges: int = 3
	cooldown: float = 8.0
	throw_speed: float = 18.0
	smoke_radius: float = 2.5
	duration: float = 7.0

	def cast(self, world, caster_slot, aim_dir):
		p = world.players[caster_slot]
		origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
		vel = aim_dir * self.throw_speed + Vec3(0, 0.5, 0)
		world.spawn_projectile(
			Projectile(origin, vel, p.team, behavior="smoke",
				owner_slot=caster_slot,
				params={"radius": self.smoke_radius, "duration": self.duration})
		)


@dataclass(slots=True)
class UpdraftAbility(IAbility):
	"""上衝：瞬間向上跳躍（Jett Updraft）。"""
	name: str = "updraft"
	charges: int = 2
	cooldown: float = 10.0
	jump_speed: float = 8.0

	def cast(self, world, caster_slot, aim_dir):
		p = world.players[caster_slot]
		p.vel = Vec3(p.vel.x, self.jump_speed, p.vel.z)
		p.movement.on_ground = False
		world.event_log.append(f"updraft: slot{caster_slot}")


@dataclass(slots=True)
class TailwindAbility(IAbility):
	"""衝刺：瞬間水平衝刺（Jett Tailwind — E 技能）。"""
	name: str = "tailwind"
	charges: int = 2
	cooldown: float = 6.0
	dash_speed: float = 12.0
	duration: float = 0.4

	def cast(self, world, caster_slot, aim_dir):
		p = world.players[caster_slot]
		dash = aim_dir * self.dash_speed
		p.vel = Vec3(dash.x, p.vel.y, dash.z)
		p.status.apply(SPEED_BOOST, self.duration, 0.5)
		world.event_log.append(f"tailwind: slot{caster_slot}")


# ====================================================================== #
# 10 名核心特務定義（C/Q/E/X 四技能）
# ====================================================================== #
# 技能順序：[C, Q, E, X]（終極技能 X 用 charges 表示充能）

# ─── 決鬥者 (Duelist) ───

AGENT_JETT = ("捷提", [
    CloudburstAbility(),      # C: Cloudburst 煙雲
    UpdraftAbility(),         # Q: Updraft 上衝
    TailwindAbility(),        # E: Tailwind 衝刺
    ThrownKnifeAbility(),     # X: Blade Storm 飛刀
])

AGENT_YORU = ("夜露", [
    FakeFootstepAbility(),    # C: Fakeout 假身
    NearsightLineAbility(),   # Q: Blindside 盲襲（穿牆閃光）
    TeleportAbility(),        # E: Gatecrash 破門（傳送）
    InvisibilityAbility(),    # X: Dimensional Drift 次元漂移
])

AGENT_NEON = ("霓虹", [
    ElectricWallAbility(),    # C: Fast Lane 快速通道（電牆）
    SlowOrbAbility(),         # Q: Relay Bolt 接力閃電（減速球近似）
    SprintAbility(),          # E: High Gear 高速檔（衝刺）
    ElectricBeamUltAbility(), # X: Overdrive 過載（閃電光束）
])

# ─── 偵查者 (Initiator) ───

AGENT_SOVA = ("蘇法", [
    FragAbility(),            # C: Shock Bolt 震擊箭（近似 frag）
    OwlDroneAbility(),        # Q: Owl Drone 貓頭鷹無人機
    ReconBoltAbility(),       # E: Recon Bolt 偵查箭
    HunterFuryAbility(),      # X: Hunter's Fury 獵手之怒
])

AGENT_BREACH = ("布雷奇", [
    AftershockAbility(),      # C: Aftershock 餘震（穿牆爆炸）
    FaultLineAbility(),       # Q: Fault Line 斷層（穿牆暈眩）
    FlashpointAbility(),      # E: Flash 閃光（反彈閃光彈）
    EarthquakeAbility(),      # X: Rolling Earthquake 滾動地震
])

AGENT_KAYO = ("凱歐", [
    FragAbility(),            # C: Fraggy 碎片（近似 frag）
    FlashpointAbility(),      # Q: Flashing 閃光
    SuppressionFieldAbility(), # E: ZERO/point 零點（範圍技能封鎖）
    NULLCmdAbility(),          # X: NULL/cmd 空指令（大範圍封鎖）
])

# ─── 控場者 (Controller) ───

AGENT_OMEN = ("幽影", [
    NearsightLineAbility(),   # C: Paranoia 偏執（穿牆近視彈）
    TeleportAbility(),        # Q: Shrouded Step 暗影步（傳送）
    SkySmokeAbility(),        # E: Dark Cover 黑暗屏障（遠程煙霧）
    InvisibilityAbility(),    # X: From the Shadows 來自暗影（隱形傳送）
])

AGENT_BRIMSTONE = ("布里姆", [
    StimBeaconAbility(),      # C: Stim Beacon 刺激信標
    IncendiaryAbility(),      # Q: Incendiary 燃燒彈
    SkySmokeAbility(),        # E: Sky Smoke 空投煙霧
    OrbitalStrikeAbility(),   # X: Orbital Strike 軌道打擊
])

AGENT_VIPER = ("薇勞", [
    ToxicScreenAbility(),     # C: Snake Bite 蛇吻（近似毒牆短版）
    SlowOrbAbility(),         # Q: Poison Cloud 毒雲（近似減速球）
    ToxicScreenAbility(),     # E: Toxic Screen 毒幕
    ViperPitAbility(),        # X: Viper's Pit 毒蛇之穴
])

# ─── 哨衛 (Sentinel) ───

AGENT_SAGE = ("賢者", [
    SlowOrbAbility(),         # C: Slow Orb 緩速球
    BarrierWallAbility(),     # Q: Barrier Orb 屏障球（冰牆）
    HealingOrbAbility(),      # E: Healing Orb 治療球
    ResurrectionAbility(),    # X: Resurrection 復活
])

# ─── AGENT 字典 ───

AGENTS: dict[str, tuple[str, list[IAbility]]] = {
    "jett": AGENT_JETT,
    "yoru": AGENT_YORU,
    "neon": AGENT_NEON,
    "sova": AGENT_SOVA,
    "breach": AGENT_BREACH,
    "kayo": AGENT_KAYO,
    "omen": AGENT_OMEN,
    "brimstone": AGENT_BRIMSTONE,
    "viper": AGENT_VIPER,
    "sage": AGENT_SAGE,
    # 通用原型補滿到 4 招（對齊 Valorant C/Q/E/X 標準）
    "assault": ("Assault", [FlashAbility(), FragAbility(), SmokeAbility(), StimAbility()]),
    "sentinel": ("Sentinel", [DeployableAbility(), SlowOrbAbility(), FragAbility(), HealingOrbAbility()]),
    "duelist": ("Duelist", [FlashAbility(), FragAbility(), SmokeAbility(), SprintAbility()]),
    "controller": ("Controller", [SmokeAbility(), DeployableAbility(), FlashAbility(), SuppressionFieldAbility()]),
}

GENERATED_AGENTS: dict[str, tuple[str, list[IAbility]]] = {}


def lookup_agent(key: str) -> tuple[str, list[IAbility]] | None:
    if key in AGENTS:
        return AGENTS[key]
    return GENERATED_AGENTS.get(key)


# ====================================================================== #
# Enhanced Ability Effect Implementations
# ====================================================================== #
# The cast() methods above handle projectile spawning, deployable creation,
# and status application. The classes below add EFFECT EVENT emission for
# client-side visual rendering, and enhanced world-effect integration.
# ====================================================================== #

class AbilityEffectEvent:
    """Data payload sent to clients for rendering ability effects."""

    def __init__(self, effect_type: str, **kwargs):
        self.effect_type = effect_type
        self.data = kwargs

    def to_dict(self) -> dict:
        return {"effect": self.effect_type, **self.data}


class AbilityEffectManager:
    """Manages active ability effects in the world (smokes, zones, walls).

    Attached to the World. Handles duration, damage ticks, and cleanup.
    """

    def __init__(self):
        self.active_zones: list[_AbilityZone] = []
        self.pending_events: list[AbilityEffectEvent] = []

    def add_zone(self, zone: _AbilityZone) -> None:
        self.active_zones.append(zone)

    def emit_event(self, event: AbilityEffectEvent) -> None:
        self.pending_events.append(event)

    def update(self, dt: float, world) -> list[dict]:
        """Tick all active zones, return pending events for network broadcast."""
        events = []
        for zone in self.active_zones:
            zone.update(dt, world)
            if zone.expired:
                zone.on_expire(world)
            else:
                events.append(zone.event_dict())
        self.active_zones = [z for z in self.active_zones if not z.expired]
        # Collect effect events
        for ev in self.pending_events:
            events.append(ev.to_dict())
        self.pending_events.clear()
        return events

    def clear(self) -> None:
        self.active_zones.clear()
        self.pending_events.clear()


class _AbilityZone:
    """Base class for persistent ability effects in the world."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        self.center = center
        self.radius = radius
        self.duration = duration
        self.time_left = duration
        self.team = team
        self.expired = False

    def update(self, dt: float, world) -> None:
        self.time_left -= dt
        if self.time_left <= 0.0:
            self.expired = True

    def on_expire(self, world) -> None:
        pass

    def event_dict(self) -> dict:
        return {}


# ─── Jett Enhanced Effects ─────────────────────────────────────

class _JettSmokeZone(_AbilityZone):
    """Cloudburst smoke cloud — blocks LOS, fades out at end."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)
        self.cloud = SmokeCloud(center, radius, duration, None)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        self.cloud.time_left = self.time_left

    def event_dict(self) -> dict:
        return {
            "effect": "smoke",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _JettDashTrail(_AbilityZone):
    """Tailwind dash trail — visual line from origin to destination."""

    def __init__(self, origin: Vec3, dest: Vec3, team: int):
        duration = 0.8
        super().__init__(origin, origin.distance_to(dest), duration, team)
        self.dest = dest

    def event_dict(self) -> dict:
        return {
            "effect": "teleport",
            "from": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "to": {"x": self.dest.x, "y": self.dest.y, "z": self.dest.z},
            "duration": self.time_left,
        }


class _JettKnifeBarrage(_AbilityZone):
    """Blade Storm — knife trail particles at origin."""

    def __init__(self, origin: Vec3, direction: Vec3, team: int):
        super().__init__(origin, 1.0, 0.5, team)
        self.direction = direction

    def event_dict(self) -> dict:
        return {
            "effect": "frag",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
        }


# ─── Sage Enhanced Effects ─────────────────────────────────────

class _SageSlowZone(_AbilityZone):
    """Slow Orb — icy ground zone that applies SLOW to enemies inside."""

    def __init__(self, center: Vec3, radius: float, duration: float, potency: float, team: int):
        super().__init__(center, radius, duration, team)
        self.potency = potency

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                if p.pos.distance_to(self.center) <= self.radius:
                    p.status.apply(SLOW, 0.5, self.potency)

    def event_dict(self) -> dict:
        return {
            "effect": "slow_zone",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _SageHealEffect(_AbilityZone):
    """Healing Orb — green healing particles on target."""

    def __init__(self, target_slot: int, amount: float, team: int):
        super().__init__(Vec3.ZERO, 0.5, 1.5, team)
        self.target_slot = target_slot
        self.amount = amount

    def event_dict(self) -> dict:
        return {
            "effect": "heal",
            "target_slot": self.target_slot,
            "amount": self.amount,
            "team": self.team,
        }


class _SageWallEffect(_AbilityZone):
    """Barrier Orb — deployable ice wall with visual indicator."""

    def __init__(self, center: Vec3, length: float, height: float, duration: float, team: int):
        super().__init__(center, length * 0.5, duration, team)
        self.wall_height = height

    def event_dict(self) -> dict:
        return {
            "effect": "wall",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "height": self.wall_height,
            "time_left": self.time_left,
            "team": self.team,
        }


class _SageResurrectEffect(_AbilityZone):
    """Resurrection — revival visual effect on the revived player."""

    def __init__(self, target_slot: int, pos: Vec3, team: int):
        super().__init__(pos, 2.0, 2.0, team)
        self.target_slot = target_slot

    def event_dict(self) -> dict:
        return {
            "effect": "heal",
            "target_slot": self.target_slot,
            "amount": 100.0,
            "team": self.team,
        }


# ─── Brimstone Enhanced Effects ────────────────────────────────

class _BrimStimZone(_AbilityZone):
    """Stim Beacon — attack speed buff zone for allies."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            for p in world.players:
                if p.alive and p.team == self.team:
                    if p.pos.distance_to(self.center) <= self.radius:
                        p.status.apply(SPEED_BOOST, 0.3, 0.3)

    def event_dict(self) -> dict:
        return {
            "effect": "trap",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "team": self.team,
        }


class _BrimIncendiaryZone(_AbilityZone):
    """Incendiary — fire damage zone on the ground."""

    def __init__(self, center: Vec3, radius: float, damage: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)
        self.dps = damage

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                if p.pos.distance_to(self.center) <= self.radius:
                    p.apply_damage(self.dps * dt, source_slot=-1, weapon_key="incendiary")

    def event_dict(self) -> dict:
        return {
            "effect": "frag",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _BrimSmokeEffect(_AbilityZone):
    """Sky Smoke — elevated smoke cloud."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)
        self.cloud = SmokeCloud(center, radius, duration, None)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        self.cloud.time_left = self.time_left

    def event_dict(self) -> dict:
        return {
            "effect": "smoke",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _BrimOrbitalStrike(_AbilityZone):
    """Orbital Strike — delayed area damage from above."""

    def __init__(self, center: Vec3, radius: float, damage: float, delay: float, team: int):
        super().__init__(center, radius, delay + 1.5, team)
        self.damage = damage
        self.delay = delay
        self.strike_applied = False

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        # Apply damage after delay
        if not self.strike_applied and self.time_left <= self.duration - self.delay:
            self.strike_applied = True
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                if p.pos.distance_to(self.center) <= self.radius:
                    p.apply_damage(self.damage, source_slot=-1, weapon_key="orbital_strike")

    def event_dict(self) -> dict:
        remaining_delay = max(0.0, self.time_left - (self.duration - self.delay))
        return {
            "effect": "frag",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
            "delay": remaining_delay,
        }


# ─── Enhanced Agent Ability Wrappers ───────────────────────────
# These wrap the existing cast() methods to also emit effect events
# and register zones with the AbilityEffectManager.

def _ensure_effect_manager(world):
    """Get or create the AbilityEffectManager on the world."""
    if not hasattr(world, 'ability_effects'):
        world.ability_effects = AbilityEffectManager()
    return world.ability_effects


def enhanced_jett_cloudburst(world, caster_slot, aim_dir):
    """Enhanced Cloudburst: spawn smoke + emit effect event."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
    vel = aim_dir * 18.0 + Vec3(0, 0.5, 0)
    world.spawn_projectile(
        Projectile(origin, vel, p.team, behavior="smoke",
            owner_slot=caster_slot,
            params={"radius": 2.5, "duration": 7.0})
    )
    mgr = _ensure_effect_manager(world)
    # Estimate landing position (approximate: origin + velocity * time_to_land)
    t_land = 0.8
    land_pos = origin + vel * t_land
    land_pos = Vec3(land_pos.x, 0.5, land_pos.z)
    zone = _JettSmokeZone(land_pos, 2.5, 7.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("smoke",
        center={"x": land_pos.x, "y": land_pos.y, "z": land_pos.z},
        radius=2.5, duration=7.0, team=p.team))
    world.event_log.append(f"cloudburst: slot{caster_slot} smoke at {land_pos}")


def enhanced_jett_tailwind(world, caster_slot, aim_dir):
    """Enhanced Tailwind: dash + trail effect."""
    p = world.players[caster_slot]
    dash = aim_dir * 12.0
    p.vel = Vec3(dash.x, p.vel.y, dash.z)
    p.status.apply(SPEED_BOOST, 0.4, 0.5)
    dest = p.pos + Vec3(dash.x * 0.03, 0, dash.z * 0.03)
    mgr = _ensure_effect_manager(world)
    zone = _JettDashTrail(p.pos, dest, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("teleport",
        from_pos={"x": p.pos.x, "y": p.pos.y, "z": p.pos.z},
        to={"x": dest.x, "y": dest.y, "z": dest.z},
        duration=0.8))
    world.event_log.append(f"tailwind: slot{caster_slot} dash {p.pos} -> {dest}")


def enhanced_jett_blade_storm(world, caster_slot, aim_dir):
    """Enhanced Blade Storm: knife barrage + visual effect."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
    import math
    for i in range(5):
        offset_angle = (i - 2) * 2.0
        rad = math.radians(offset_angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        dir_v = Vec3(
            aim_dir.x * cos_a - aim_dir.z * sin_a,
            aim_dir.y,
            aim_dir.x * sin_a + aim_dir.z * cos_a,
        )
        world.spawn_projectile(
            Projectile(origin, dir_v * 35.0, p.team,
                gravity=0.0, bounce_restitution=0.0, max_bounces=0,
                fuse_time=1.5, damage=50.0,
                explosion_radius=0.6, behavior="line_hit",
                owner_slot=caster_slot,
                params={"radius": 0.6, "damage": 50.0})
        )
    mgr = _ensure_effect_manager(world)
    zone = _JettKnifeBarrage(origin, aim_dir, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("frag",
        center={"x": origin.x, "y": origin.y, "z": origin.z},
        radius=1.0))
    world.event_log.append(f"blade_storm: slot{caster_slot} fired 5 knives")


def enhanced_sage_slow_orb(world, caster_slot, aim_dir):
    """Enhanced Slow Orb: projectile + ground slow zone."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
    vel = aim_dir * 14.0 + Vec3(0, 2.0, 0)
    world.spawn_projectile(
        Projectile(origin, vel, p.team, behavior="slow_orb",
            owner_slot=caster_slot,
            params={"radius": 4.0, "duration": 5.0, "potency": 1.0})
    )
    mgr = _ensure_effect_manager(world)
    # Landing zone
    t_land = 0.7
    land_pos = origin + vel * t_land
    land_pos = Vec3(land_pos.x, 0.1, land_pos.z)
    zone = _SageSlowZone(land_pos, 4.0, 5.0, 1.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("slow_zone",
        center={"x": land_pos.x, "y": land_pos.y, "z": land_pos.z},
        radius=4.0, duration=5.0, team=p.team))
    world.event_log.append(f"slow_orb: slot{caster_slot} zone at {land_pos}")


def enhanced_sage_barrier_orb(world, caster_slot, aim_dir):
    """Enhanced Barrier Orb: deployable wall + visual event."""
    p = world.players[caster_slot]
    from server.game.mapdata import Wall
    center = p.pos + aim_dir * 2.5
    perp = Vec3(-aim_dir.z, 0, aim_dir.x)
    if perp.length_sq() > 0.01:
        perp = perp.normalized()
    wall_length = 5.0
    wall_height = 3.5
    mn = Vec3(
        center.x - perp.x * wall_length * 0.5, 0,
        center.z - perp.z * wall_length * 0.5)
    mx = Vec3(
        center.x + perp.x * wall_length * 0.5, wall_height,
        center.z + perp.z * wall_length * 0.5)
    temp_wall = Wall(mn, mx, "concrete")
    world.map_data.walls.append(temp_wall)
    world.map_data._ray_hash = None
    wall_entity = _TimedWall(temp_wall, world.map_data, 15.0, "solid", p.team)
    world.deployables.append(wall_entity)
    mgr = _ensure_effect_manager(world)
    zone = _SageWallEffect(center, wall_length, wall_height, 15.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("wall",
        center={"x": center.x, "y": center.y, "z": center.z},
        length=wall_length, height=wall_height, duration=15.0, team=p.team))
    world.event_log.append(f"barrier_orb: slot{caster_slot} wall at {center}")


def enhanced_sage_healing_orb(world, caster_slot, aim_dir):
    """Enhanced Healing Orb: heal nearest ally + visual effect."""
    p = world.players[caster_slot]
    heal_amount = 60.0
    # Find nearest alive ally (excluding self)
    best_slot = -1
    best_dist = 999.0
    for slot, target in enumerate(world.players):
        if slot == caster_slot or not target.alive or target.team != p.team:
            continue
        d = p.pos.distance_to(target.pos)
        if d < best_dist and d < 10.0:
            best_dist = d
            best_slot = slot
    if best_slot >= 0:
        target = world.players[best_slot]
        target.health = min(100.0, target.health + heal_amount)
        mgr = _ensure_effect_manager(world)
        zone = _SageHealEffect(best_slot, heal_amount, p.team)
        mgr.add_zone(zone)
        mgr.emit_event(AbilityEffectEvent("heal",
            target_slot=best_slot, amount=heal_amount, team=p.team))
        world.event_log.append(f"heal_orb: slot{caster_slot} healed slot{best_slot} +{heal_amount}hp")
    else:
        # No ally nearby: heal self
        p.health = min(100.0, p.health + heal_amount)
        mgr = _ensure_effect_manager(world)
        zone = _SageHealEffect(caster_slot, heal_amount, p.team)
        mgr.add_zone(zone)
        mgr.emit_event(AbilityEffectEvent("heal",
            target_slot=caster_slot, amount=heal_amount, team=p.team))
        world.event_log.append(f"heal_orb: slot{caster_slot} self-heal +{heal_amount}hp")


def enhanced_sage_resurrection(world, caster_slot, aim_dir):
    """Enhanced Resurrection: revive + resurrection visual effect."""
    caster = world.players[caster_slot]
    best_slot = -1
    best_dist = 999.0
    for slot, p in enumerate(world.players):
        if not p.alive and p.team == caster.team:
            d = p.pos.distance_to(caster.pos)
            if d < best_dist:
                best_dist = d
                best_slot = slot
    if best_slot >= 0:
        target = world.players[best_slot]
        target.alive = True
        target.health = 100.0
        target.shield_hp = 0.0
        target.pos = caster.pos + aim_dir * 1.0
        target.vel = Vec3()
        mgr = _ensure_effect_manager(world)
        zone = _SageResurrectEffect(best_slot, target.pos, caster.team)
        mgr.add_zone(zone)
        mgr.emit_event(AbilityEffectEvent("heal",
            target_slot=best_slot, amount=100.0, team=caster.team))
        world.event_log.append(f"resurrection: slot{caster_slot} revived slot{best_slot}")


def enhanced_brim_stim_beacon(world, caster_slot, aim_dir):
    """Enhanced Stim Beacon: zone buff + trap visual."""
    p = world.players[caster_slot]
    beacon = _StimBeacon(p.pos, p.team, 4.0, 8.0)
    world.deployables.append(beacon)
    mgr = _ensure_effect_manager(world)
    zone = _BrimStimZone(p.pos, 4.0, 8.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("trap",
        center={"x": p.pos.x, "y": p.pos.y, "z": p.pos.z},
        radius=4.0, team=p.team))
    world.event_log.append(f"stim_beacon: slot{caster_slot} at {p.pos}")


def enhanced_brim_incendiary(world, caster_slot, aim_dir):
    """Enhanced Incendiary: projectile → fire damage zone."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
    world.spawn_projectile(
        Projectile(origin, aim_dir * 14.0, p.team,
            behavior="flame", max_bounces=1, fuse_time=0.5,
            owner_slot=caster_slot,
            params={"radius": 3.0, "damage": 40.0, "duration": 6.0})
    )
    mgr = _ensure_effect_manager(world)
    t_land = 0.6
    land_pos = origin + aim_dir * 14.0 * t_land
    land_pos = Vec3(land_pos.x, 0.1, land_pos.z)
    zone = _BrimIncendiaryZone(land_pos, 3.0, 40.0, 6.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("frag",
        center={"x": land_pos.x, "y": land_pos.y, "z": land_pos.z},
        radius=3.0, duration=6.0, team=p.team))
    world.event_log.append(f"incendiary: slot{caster_slot} fire at {land_pos}")


def enhanced_brim_sky_smoke(world, caster_slot, aim_dir):
    """Enhanced Sky Smoke: up to 3 smokes at target locations."""
    p = world.players[caster_slot]
    # Primary smoke at aim direction
    target = p.pos + aim_dir * 15.0
    target = Vec3(target.x, 0, target.z)
    cloud = SmokeCloud(target, 3.5, 14.0, world.rng)
    world.smokes.append(cloud)
    mgr = _ensure_effect_manager(world)
    zone = _BrimSmokeEffect(target, 3.5, 14.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("smoke",
        center={"x": target.x, "y": target.y, "z": target.z},
        radius=3.5, duration=14.0, team=p.team))
    world.event_log.append(f"sky_smoke: slot{caster_slot} at {target}")


def enhanced_brim_orbital_strike(world, caster_slot, aim_dir):
    """Enhanced Orbital Strike: delayed area nuke + warning indicator."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0)
    hit = world.map_data.raycast(origin, aim_dir, 30.0)
    target_pos = hit.point if hit is not None else p.pos + aim_dir * 10.0
    # Warning indicator
    mgr = _ensure_effect_manager(world)
    zone = _BrimOrbitalStrike(target_pos, 5.0, 150.0, 2.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("frag",
        center={"x": target_pos.x, "y": target_pos.y, "z": target_pos.z},
        radius=5.0, delay=2.0, team=p.team))
    # Also spawn the delayed strike deployable for authoritative damage
    strike = _DelayedStrike(target_pos, p.team, 5.0, 150.0, 2.0)
    world.deployables.append(strike)
    world.event_log.append(f"orbital_strike: slot{caster_slot} targeting {target_pos}")


# ─── Viper Enhanced Effects ──────────────────────────────────

class _ToxicWall(_AbilityZone):
    """Toxic Screen — line deployable that applies DECAY to enemies crossing it."""

    def __init__(self, origin: Vec3, direction: Vec3, length: float, duration: float, team: int):
        self.origin = origin
        self.direction = direction
        self.length = length
        super().__init__(origin, 2.5, duration, team)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                # Project player onto the wall line and check distance
                to_player = p.pos - self.origin
                proj = to_player.x * self.direction.x + to_player.z * self.direction.z
                if 0.0 <= proj <= self.length:
                    perp = Vec3(to_player.x - self.direction.x * proj, 0,
                                to_player.z - self.direction.z * proj)
                    if perp.length_sq() <= self.radius * self.radius:
                        p.status.apply(DECAY, 0.5, 1.0)

    def event_dict(self) -> dict:
        end = self.origin + self.direction * self.length
        return {
            "effect": "toxic_wall",
            "origin": {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z},
            "end": {"x": end.x, "y": end.y, "z": end.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _ViperToxicScreen(_AbilityZone):
    """Toxic Screen — visual indicator for the toxic gas wall."""

    def __init__(self, origin: Vec3, direction: Vec3, length: float, duration: float, team: int):
        super().__init__(origin, 2.5, duration, team)
        self.direction = direction
        self.length = length

    def event_dict(self) -> dict:
        end = self.origin + self.direction * self.length
        return {
            "effect": "toxic_wall",
            "origin": {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z},
            "end": {"x": end.x, "y": end.y, "z": end.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _ViperPit(_AbilityZone):
    """Viper's Pit — massive dome that applies DECAY and reduces enemy vision."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                if p.pos.distance_to(self.center) <= self.radius:
                    p.status.apply(DECAY, 0.5, 1.0)
                    p.status.apply(NEARSIGHT, 0.5, 0.0)

    def event_dict(self) -> dict:
        return {
            "effect": "viper_pit",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


# ─── Sova Enhanced Effects ───────────────────────────────────

class _ReconZone(_AbilityZone):
    """Recon Bolt — pulses every 2s revealing enemies, tracks pulse count."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)
        self.pulse_interval = 2.0
        self.pulse_timer = 0.0
        self.max_pulses = 3
        self.pulses_done = 0

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.expired:
            self.pulse_timer += dt
            if self.pulse_timer >= self.pulse_interval:
                self.pulse_timer -= self.pulse_interval
                self.pulses_done += 1
                if self.pulses_done <= self.max_pulses:
                    for slot, p in enumerate(world.players):
                        if not p.alive or p.team == self.team:
                            continue
                        if p.pos.distance_to(self.center) <= self.radius:
                            p.status.apply(REVEALED, 1.5, 1.0)
                    # Additional pulse event
                    if hasattr(world, 'ability_events_extra'):
                        world.ability_events_extra.append({
                            "effect": "recon_pulse",
                            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
                            "radius": self.radius,
                            "pulse": self.pulses_done,
                            "team": self.team,
                        })

    def event_dict(self) -> dict:
        return {
            "effect": "recon",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "pulse": self.pulses_done,
            "team": self.team,
        }


class _SovaReconBoltEffect(_AbilityZone):
    """Recon Bolt — visual indicator on landing spot."""

    def __init__(self, center: Vec3, radius: float, duration: float, team: int):
        super().__init__(center, radius, duration, team)

    def event_dict(self) -> dict:
        return {
            "effect": "recon",
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "radius": self.radius,
            "time_left": self.time_left,
            "team": self.team,
        }


class _HunterFuryEffect(_AbilityZone):
    """Hunter's Fury — visual indicator for energy blasts."""

    def __init__(self, origin: Vec3, direction: Vec3, team: int):
        super().__init__(origin, 2.0, 0.6, team)
        self.direction = direction

    def event_dict(self) -> dict:
        end = self.origin + self.direction * 20.0
        return {
            "effect": "hunter_fury",
            "origin": {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z},
            "end": {"x": end.x, "y": end.y, "z": end.z},
            "team": self.team,
        }


# ─── Omen Enhanced Effects ───────────────────────────────────

class _OmenTeleportEffect(_AbilityZone):
    """Shrouded Step — teleport windup visual effect."""

    def __init__(self, origin: Vec3, dest: Vec3, team: int):
        super().__init__(origin, 1.0, 0.5, team)
        self.dest = dest

    def event_dict(self) -> dict:
        return {
            "effect": "teleport",
            "from": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "to": {"x": self.dest.x, "y": self.dest.y, "z": self.dest.z},
            "duration": self.time_left,
            "team": self.team,
        }


# ─── Breach Enhanced Effects ─────────────────────────────────

class _BreachFaultLine(_AbilityZone):
    """Fault Line — stun line through walls."""

    def __init__(self, origin: Vec3, direction: Vec3, length: float, team: int):
        super().__init__(origin, 2.0, 0.3, team)
        self.direction = direction
        self.length = length
        self.applied = False

    def update(self, dt: float, world) -> None:
        super().update(dt, world)
        if not self.applied and not self.expired:
            self.applied = True
            for slot, p in enumerate(world.players):
                if not p.alive or p.team == self.team:
                    continue
                to_player = p.pos - self.origin
                proj = to_player.x * self.direction.x + to_player.z * self.direction.z
                if 0.0 <= proj <= self.length:
                    perp = Vec3(to_player.x - self.direction.x * proj, 0,
                                to_player.z - self.direction.z * proj)
                    if perp.length_sq() <= 4.0:
                        p.status.apply(CONCUSS, 3.0, 1.0)
                        p.apply_damage(30.0, source_slot=-1, weapon_key="fault_line")

    def event_dict(self) -> dict:
        end = self.origin + self.direction * self.length
        return {
            "effect": "fault_line",
            "origin": {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z},
            "end": {"x": end.x, "y": end.y, "z": end.z},
            "team": self.team,
        }


class _BreachFaultLineEffect(_AbilityZone):
    """Fault Line — visual indicator for the stun line."""

    def __init__(self, origin: Vec3, direction: Vec3, length: float, team: int):
        super().__init__(origin, 2.0, 0.3, team)
        self.direction = direction
        self.length = length

    def event_dict(self) -> dict:
        end = self.origin + self.direction * self.length
        return {
            "effect": "fault_line",
            "origin": {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z},
            "end": {"x": end.x, "y": end.y, "z": end.z},
            "team": self.team,
        }


# ─── Neon Enhanced Effects ───────────────────────────────────

class _NeonSprintEffect(_AbilityZone):
    """High Gear — speed boost visual indicator."""

    def __init__(self, slot: int, duration: float, team: int):
        super().__init__(Vec3.ZERO, 0.5, duration, team)
        self.slot = slot

    def event_dict(self) -> dict:
        return {
            "effect": "sprint",
            "slot": self.slot,
            "time_left": self.time_left,
            "team": self.team,
        }


# ─── Enhanced Viper Abilities ────────────────────────────────

def enhanced_viper_toxic_screen(world, caster_slot, aim_dir):
    """Enhanced Toxic Screen: line of toxic gas — blocks LOS, applies DECAY."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.0, 0)
    wall_length = 20.0
    # Spawn deployable toxic wall
    toxic_wall = _ToxicWall(origin, aim_dir, wall_length, 8.0, p.team)
    world.deployables.append(toxic_wall)
    mgr = _ensure_effect_manager(world)
    zone = _ViperToxicScreen(origin, aim_dir, wall_length, 8.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("toxic_wall",
        origin={"x": origin.x, "y": origin.y, "z": origin.z},
        direction={"x": aim_dir.x, "y": aim_dir.y, "z": aim_dir.z},
        length=wall_length, duration=8.0, team=p.team))
    world.event_log.append(f"toxic_screen: slot{caster_slot} wall from {origin}")


def enhanced_viper_pit(world, caster_slot, aim_dir):
    """Enhanced Viper's Pit: massive dome — DECAY + reduced vision, 12s."""
    p = world.players[caster_slot]
    center = p.pos + Vec3(0, 0.5, 0)
    radius = 10.0
    duration = 12.0
    mgr = _ensure_effect_manager(world)
    zone = _ViperPit(center, radius, duration, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("viper_pit",
        center={"x": center.x, "y": center.y, "z": center.z},
        radius=radius, duration=duration, team=p.team))
    world.event_log.append(f"viper_pit: slot{caster_slot} dome at {center}")


# ─── Enhanced Sova Abilities ─────────────────────────────────

def enhanced_sova_recon_bolt(world, caster_slot, aim_dir):
    """Enhanced Recon Bolt: projectile that lands, pulses every 2s revealing enemies."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0) + aim_dir * 0.5
    vel = aim_dir * 16.0 + Vec3(0, 3.0, 0)
    world.spawn_projectile(
        Projectile(origin, vel, p.team, behavior="recon_bolt",
            owner_slot=caster_slot,
            params={"radius": 8.0, "duration": 6.0})
    )
    mgr = _ensure_effect_manager(world)
    t_land = 0.6
    land_pos = origin + vel * t_land
    land_pos = Vec3(land_pos.x, 0.3, land_pos.z)
    zone = _ReconZone(land_pos, 8.0, 6.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("recon",
        center={"x": land_pos.x, "y": land_pos.y, "z": land_pos.z},
        radius=8.0, duration=6.0, team=p.team))
    world.event_log.append(f"recon_bolt: slot{caster_slot} landed at {land_pos}")


def enhanced_sova_hunter_fury(world, caster_slot, aim_dir):
    """Enhanced Hunter's Fury: 3 energy blasts through walls, 80 dmg each."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.5, 0)
    blast_radius = 2.0
    blast_damage = 80.0
    import math
    for i in range(3):
        # Slight spread between blasts
        offset_angle = (i - 1) * 3.0
        rad = math.radians(offset_angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        blast_dir = Vec3(
            aim_dir.x * cos_a - aim_dir.z * sin_a,
            aim_dir.y,
            aim_dir.x * sin_a + aim_dir.z * cos_a,
        )
        world.spawn_projectile(
            Projectile(origin, blast_dir * 40.0, p.team,
                gravity=0.0, fuse_time=0.3, damage=blast_damage,
                explosion_radius=blast_radius, behavior="line_hit",
                owner_slot=caster_slot,
                params={"radius": blast_radius, "damage": blast_damage,
                        "through_walls": True})
        )
    mgr = _ensure_effect_manager(world)
    zone = _HunterFuryEffect(origin, aim_dir, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("hunter_fury",
        origin={"x": origin.x, "y": origin.y, "z": origin.z},
        direction={"x": aim_dir.x, "y": aim_dir.y, "z": aim_dir.z},
        blasts=3, damage=blast_damage, team=p.team))
    world.event_log.append(f"hunter_fury: slot{caster_slot} 3 blasts from {origin}")


# ─── Enhanced Omen Abilities ─────────────────────────────────

def enhanced_omen_teleport(world, caster_slot, aim_dir):
    """Enhanced Shrouded Step: instant teleport 15m, 0.5s windup with NEARSIGHT."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 0, 0)
    dest = origin + aim_dir * 15.0
    # Apply NEARSIGHT to self during windup
    p.status.apply(NEARSIGHT, 0.5, 0.0)
    mgr = _ensure_effect_manager(world)
    zone = _OmenTeleportEffect(origin, dest, p.team)
    mgr.add_zone(zone)
    # Teleport after windup (immediate for simplicity, windup is visual only)
    p.pos = dest
    p.vel = Vec3()
    mgr.emit_event(AbilityEffectEvent("teleport",
        from_pos={"x": origin.x, "y": origin.y, "z": origin.z},
        to={"x": dest.x, "y": dest.y, "z": dest.z},
        windup=0.5, team=p.team))
    world.event_log.append(f"omen_teleport: slot{caster_slot} {origin} -> {dest}")


# ─── Enhanced Breach Abilities ───────────────────────────────

def enhanced_breach_fault_line(world, caster_slot, aim_dir):
    """Enhanced Fault Line: stun line through walls — CONCUSS 3s + 30 damage."""
    p = world.players[caster_slot]
    origin = p.pos + Vec3(0, 1.0, 0)
    line_length = 10.0
    mgr = _ensure_effect_manager(world)
    zone = _BreachFaultLine(origin, aim_dir, line_length, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("fault_line",
        origin={"x": origin.x, "y": origin.y, "z": origin.z},
        direction={"x": aim_dir.x, "y": aim_dir.y, "z": aim_dir.z},
        length=line_length, team=p.team))
    world.event_log.append(f"fault_line: slot{caster_slot} line from {origin}")


# ─── Enhanced Neon Abilities ─────────────────────────────────

def enhanced_neon_sprint(world, caster_slot, aim_dir):
    """Enhanced High Gear: SPEED_BOOST 1.3x for 8s."""
    p = world.players[caster_slot]
    p.status.apply(SPEED_BOOST, 8.0, 1.3)
    mgr = _ensure_effect_manager(world)
    zone = _NeonSprintEffect(caster_slot, 8.0, p.team)
    mgr.add_zone(zone)
    mgr.emit_event(AbilityEffectEvent("sprint",
        slot=caster_slot, duration=8.0, multiplier=1.3, team=p.team))
    world.event_log.append(f"neon_sprint: slot{caster_slot} speed boost 1.3x for 8s")
