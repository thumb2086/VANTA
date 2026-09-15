"""
server/game/entities.py — 玩家實體與世界整合
=============================================
WeaponState：單把武器的彈匣/射速/後座力/恢復狀態（伺服器權威）。
Player：移動控制器 + 生命/護甲 + 武器 + 經濟 + 狀態 + 技能。
World：10 槽位世界，串接 移動 → 彈道 → Spike → 對戰 → 技能 → 專案檔案。

相容性：World.players[i] 暴露 .pos/.vel/.on_ground/.crouching/.walking
代理（M2 測試與伺服器快照沿用）。
"""

from __future__ import annotations

import os
import random

from dataclasses import dataclass

from server.core.accuracy import MovementErrorEngine
from server.core.math_core import Vec3, dir_from_yaw_pitch
from server.core.movement import MovementConfig, MoveInput
from server.core.movement_factory import create_controller
from server.game.abilities import AbilitySystem, lookup_agent
from server.game.inventory import WeaponInventory
from server.game.ballistics import EYE_HEIGHT, Projectile, explode, resolve_hitscan
from server.game.economy import (
    HEAVY_SHIELD_HP,
    HEAVY_SHIELD_PRICE,
    KILL_REWARD,
    LIGHT_SHIELD_HP,
    LIGHT_SHIELD_PRICE,
    EconomyComponent,
)
from server.game.mapdata import SmokeCloud, default_map, DoorToggle
from server.game.recoil import RecoilController, SpreadEngine, pattern_for
from server.game.status import (
    StatusEffectSystem,
    BLIND, CONCUSS, VULNERABLE, SPEED_BOOST,
    NEARSIGHT, SUPPRESSED, DECAY, SLOW, DEAFENED, REVEALED,
)
from server.game.weapon_state import WeaponState
from server.game.weapons import WEAPONS, WeaponStats, weapon

__all__ = ["World", "Player", "PlayerMoveState", "WeaponState", "DamageReceipt"]

_MOVEMENT_ERROR = MovementErrorEngine()


@dataclass(slots=True)
class DamageReceipt:
    damage_dealt: float
    killed: bool


# ---------------------------------------------------------------------- #
# 玩家
# ---------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PlayerMoveState:
    """世界對外輸出的玩家移動狀態（供快照/測試使用）。"""

    slot: int
    pos: Vec3
    vel: Vec3
    on_ground: bool
    crouching: bool
    walking: bool


class Player:
    def __init__(self, slot: int, team: int, rng, cfg: MovementConfig | None = None,
                 ground_y: float = 0.0, agent_key: str = "assault"):
        self.slot = slot
        self.team = team
        self.world: "World | None" = None
        self.movement = create_controller(cfg, ground_y)
        self.health = 100.0
        self.alive = True
        self.shield_hp = 0.0
        self.inventory = WeaponInventory(rng)
        self.economy = EconomyComponent()
        self.status = StatusEffectSystem()
        self.agent_key = agent_key
        agent_def = lookup_agent(agent_key)
        if agent_def is None:
            raise KeyError(f"unknown agent: {agent_key}")
        self.abilities = AbilitySystem(list(agent_def[1]))
        self.kills = 0
        self.deaths = 0
        self.assists = 0
        self.damage_dealt = 0.0
        # 本回合傷害歸因：attacker_slot -> 累計傷害（助攻判定用，每回合清空）
        self.dmg_log: dict[int, float] = {}

    # --- 移動代理（M2 相容） ---
    @property
    def pos(self) -> Vec3:
        return self.movement.pos

    @pos.setter
    def pos(self, v: Vec3) -> None:
        self.movement.pos = v

    @property
    def vel(self) -> Vec3:
        return self.movement.vel

    @vel.setter
    def vel(self, v: Vec3) -> None:
        self.movement.vel = v

    @property
    def on_ground(self) -> bool:
        return self.movement.on_ground

    @property
    def crouching(self) -> bool:
        return self.movement.crouching

    @property
    def walking(self) -> bool:
        return self.movement.walking

    def step_movement(self, inp: MoveInput | None, dt: float) -> None:
        if inp is None:
            inp = MoveInput()
        # 狀態速度倍率（暈眩/刺激）作用於最大速度 — 伺服器權威
        self.movement.step(inp, dt, self.status.move_speed_mult)

    # --- 武器（作用於「目前活躍槽位」）---
    @property
    def weapon(self) -> WeaponState:
        return self.inventory.active_state()

    @weapon.setter
    def weapon(self, ws: WeaponState) -> None:
        self.inventory.install_primary(ws)
        self.inventory.active = 0

    def switch_weapon(self, slot: int) -> bool:
        """切換武器槽位（0 主 / 1 副 / 2 刀）。回傳是否成功。"""
        return self.inventory.start_switch(slot, self.world.time if self.world is not None else 0.0)

    # --- 戰鬥 ---
    def apply_damage(self, amount: float, source_slot: int = -1, weapon_key: str = "") -> DamageReceipt:
        # 攻擊方傷害加成（金槍等）：透過 world 查來源狀態
        mult = 1.0
        if self.world is not None and 0 <= source_slot < len(self.world.players):
            try:
                mult = self.world.players[source_slot].status.damage_dealt_mult
            except Exception:
                mult = 1.0
        amount = amount * mult
        # 傷害歸因（助攻判定用）：記錄攻擊者對本目標的累計傷害
        if 0 <= source_slot < 10 and source_slot != self.slot:
            self.dmg_log[source_slot] = self.dmg_log.get(source_slot, 0.0) + amount
            if self.world is not None and 0 <= source_slot < len(self.world.players):
                self.world.players[source_slot].damage_dealt += amount
        dmg = amount * self.status.damage_taken_mult
        dealt = 0.0
        if self.shield_hp > 0.0:
            absorbed = min(self.shield_hp, dmg)
            self.shield_hp -= absorbed
            dmg -= absorbed
            dealt += absorbed
        if dmg > 0.0:
            self.health -= dmg
            dealt += dmg
        killed = False
        if self.health <= 0.0 and self.alive:
            self.health = 0.0
            self.alive = False
            self.deaths += 1
            killed = True
            if self.world is not None:
                self.world._on_player_killed(self.slot, source_slot, weapon_key)
        return DamageReceipt(dealt, killed)

    # --- 武器（作用於「目前活躍槽位」）---
    @property
    def weapon(self) -> WeaponState:
        return self.inventory.active_state()

    @weapon.setter
    def weapon(self, ws: WeaponState) -> None:
        self.inventory.install_primary(ws)
        self.inventory.active = 0

    def switch_weapon(self, slot: int) -> bool:
        """切換武器槽位（0 主 / 1 副 / 2 刀）。回傳是否成功。"""
        return self.inventory.start_switch(slot, self.world.time if self.world is not None else 0.0)

    def buy_weapon(self, key: str) -> bool:
        stats = weapon(key)
        if not self.economy.buy(stats.price):
            return False
        ws = WeaponState(stats, self.inventory.active_state().rng)
        self.inventory.install_primary(ws)
        # 購買後自動切到主武器（立即生效，短門控）
        self.inventory.active = 0
        self.inventory.switch_until = max(self.inventory.switch_until,
                                          (self.world.time if self.world else 0.0) + 0.65)
        return True

    def buy_shield(self, level: int) -> bool:
        """level 1 = 輕甲 25HP，level 2 = 重甲 50HP。"""
        if level == 1:
            price, hp = LIGHT_SHIELD_PRICE, LIGHT_SHIELD_HP
        elif level == 2:
            price, hp = HEAVY_SHIELD_PRICE, HEAVY_SHIELD_HP
        else:
            return False
        if not self.economy.buy(price):
            return False
        self.shield_hp = hp
        return True

    def grant_weapon(self, key: str) -> None:
        """免費配槍（Spike Rush 配裝 / orb 升級）：不扣錢，直接裝主武器槽。"""
        from server.game.weapon_state import WeaponState
        stats = weapon(key)
        ws = WeaponState(stats, self.inventory.active_state().rng)
        self.inventory.install_primary(ws)
        self.inventory.active = 0
        self.inventory.switch_until = -1.0

    def grant_shield(self, hp: float) -> None:
        """免費護甲（Spike Rush 配裝）。"""
        self.shield_hp = hp

    def new_round(self) -> None:
        """回合開始：清空本回合傷害歸因（助攻判定窗口重置）。"""
        self.dmg_log = {}

    def update(self, now: float, dt: float) -> None:
        self.weapon.update(now, dt)
        self.status.update(dt)
        self.status.tick_decay(dt, self)  # 處理 Decay 持續傷害
        self.abilities.update(dt)
    def snapshot(self) -> dict:
        return {
            "slot": self.slot, "team": self.team, "alive": self.alive,
            "health": round(self.health, 1), "shield": self.shield_hp,
            "credits": self.economy.credits, "kills": self.kills, "deaths": self.deaths,
            "agent": self.agent_key, "weapon": self.weapon.snapshot(),
            "abilities": self.abilities.snapshot(),
        }


# ---------------------------------------------------------------------- #
# 世界
# ---------------------------------------------------------------------- #
class World:
    def __init__(self, slots: int = 10, cfg: MovementConfig | None = None,
                 ground_y: float = 0.0, seed: int = 42, map_data=None):
        self.rng = random.Random(seed)
        self.map_data = map_data if map_data is not None else default_map()
        # 前 5 槽 = 攻擊隊 (team 0)，後 5 槽 = 防守隊 (team 1)
        self.players = [
            Player(i, 0 if i < 5 else 1, self.rng, cfg, ground_y)
            for i in range(slots)
        ]
        for p in self.players:
            p.world = self
        # 出生即放置於各自隊伍的重生點（避免全員重疊於原點）
        for p in self.players:
            spawns = (
                self.map_data.spawns_attackers
                if p.team == 0
                else self.map_data.spawns_defenders
            )
            p.pos = spawns[p.slot % len(spawns)]
        self.tick = 0
        self.time = 0.0
        self.match = None
        self.spike = None
        self.projectiles: list[Projectile] = []
        self.deployables = []
        self.smokes: list[SmokeCloud] = []
        self.event_log: list[str] = []
        self.spread_engine = SpreadEngine(self.rng)
        # 好玩系統（highlight/mission/replay）：延遲掛載，不影響熱路徑
        self._highlights = None  # HighlightTracker
        self._missions: dict[int, object] = {}  # slot -> MissionTracker
        self._replay = None  # ReplayRecorder
        # 地圖互動機制狀態
        self._teleport_cooldowns: dict[int, float] = {}  # slot -> 剩餘冷卻
        self._rope_active: dict[int, int] = {}   # slot -> rope index（-1 = 未攀爬）
        self._rope_progress: dict[int, float] = {}  # slot -> 攀爬進度 0..1
        # M4：Rust 世界迴圈（VANTA_USE_RS=1 時啟用；每 tick 一次跨邊界）
        self._rs_world = None
        if os.environ.get("VANTA_USE_RS") == "1":
            try:
                from server.core import rs_bridge

                if rs_bridge.rs_available():
                    walls = [(w.mn.x, w.mn.y, w.mn.z, w.mx.x, w.mx.y, w.mx.z)
                             for w in self.map_data.walls]
                    self._rs_world = rs_bridge.RustWorldSim(
                        walls, cfg, ground_y, count=len(self.players))
                    # RustWorldSim 每 tick 寫回玩家狀態 → movement 用可寫回的 Python 控制器
                    from server.core.movement import MovementController as _PyCtl

                    for p in self.players:
                        old = p.movement
                        p.movement = _PyCtl(cfg, ground_y)
                        p.movement.pos = old.pos
                        p.movement.vel = old.vel
            except Exception:
                self._rs_world = None

    # ------------------------------------------------------------------ #
    def start_match(self, mode: str = "competitive"):
        """建立對戰（回合狀態機 + Spike）。回傳 Match 實例。"""
        from server.game.match import Match
        from server.game.spike import SpikeController

        self.match = Match(self, mode=mode)
        if mode in ("deathmatch", "teamdeathmatch"):
            self.spike = None  # 死鬥/團隊死鬥無 Spike
        else:
            self.spike = SpikeController(self, self.map_data)
        return self.match

    def step(self, inputs: list[MoveInput | None], dt: float) -> None:
        # 買槍/行動期可移動（買槍限制在出生區）；結算/結束凍結（像特戰）
        movable = self.match is None or self.match.phase.value in ("action", "buy")
        if self._rs_world is not None:
            self._rs_step(inputs, dt, movable)
        else:
            for i, p in enumerate(self.players):
                inp = inputs[i] if i < len(inputs) else None
                if not p.alive:
                    p.vel = Vec3()
                    continue
                if movable:
                    p.step_movement(inp, dt)
                else:
                    p.step_movement(None, dt)   # 結算/結束階段：人物原地煞車
                p.update(self.time, dt)

            # 移動碰撞（牆面 + 玩家間）— 在彈道/爆炸判定前完成位置修正
            from server.game.collision import resolve_world

            resolve_world(self)

        # 地圖互動機制（傳送門/繩索/鐵門）— 在碰撞前檢查傳送門
        # 以避免碰撞推離入口位置
        self._update_teleporters(dt)

        # 買槍區限制（雙路徑共用，Python 後置 → Rust 路徑行為一致）
        self._clamp_buy_zones()
        # 繩索攀爬進度（在碰撞後更新，避免碰撞推離攀爬中的玩家）
        self._update_ropes(dt)

        # ---- 其餘子系統（移動/碰撞之後，雙路徑共用）----
        # 實體彈道
        for proj in list(self.projectiles):
            ev = proj.step(dt, self.map_data)
            if ev == "detonate":
                self._detonate_projectile(proj)
            elif ev == "wall_bounce" and proj.behavior == "smoke":
                self._spawn_smoke(proj)
                self.projectiles.remove(proj)
        self.projectiles = [p for p in self.projectiles if p.pos is not None]

        # 部署物
        self.deployables = [t for t in self.deployables if not t.update(dt, self)]

        # 煙霧
        for s in self.smokes:
            s.update(dt)
        self.smokes = [s for s in self.smokes if s.active]

        if self.spike is not None:
            self.spike.update(dt)
        if self.match is not None:
            self.match.step(dt)
        # 好玩系統：highlight 播報（非阻塞）
        try:
            if self._highlights is None and self.match is not None:
                from server.game.highlights import HighlightTracker

                self._highlights = HighlightTracker()
            if self._highlights is not None and self.match is not None:
                for ann in self._highlights.update(self, self.match):
                    self.event_log.append(ann)
        except Exception:
            pass
        try:
            if self._replay is not None:
                self._replay.record_tick(self.tick, self.time, self)
                for line in self.event_log[-32:]:
                    if line.startswith(("kill:", "assist:", "orb:")):
                        self._replay.record_event(self.tick, line.split(":")[0], {"log": line})
        except Exception:
            pass

        self.tick += 1
        self.time = self.tick * dt

    def enable_replay(self, match_id: str = "", mode: str = "competitive") -> None:
        from server.game.replay import ReplayRecorder

        self._replay = ReplayRecorder()
        self._replay.record_meta(match_id or f"match_{self.tick}", mode)

    def _get_mission(self, slot: int, date_str: str | None = None) -> object:
        if slot not in self._missions:
            from server.game.missions import MissionTracker
            import datetime

            d = date_str or datetime.date.today().isoformat()
            self._missions[slot] = MissionTracker(d)
        return self._missions[slot]

    def _clamp_buy_zones(self) -> None:
        """買槍階段：玩家限制在出生區內（像《特戰英豪》——可動但不可越界）。

        行動/結算/結束階段不限制；兩路徑（Python/Rust）皆在碰撞後執行 → 一致。
        """
        if self.match is None or self.match.phase.value != "buy":
            return
        md = self.map_data
        for p in self.players:
            if not p.alive:
                continue
            zone = md.buy_zone_attackers if p.team == 0 else md.buy_zone_defenders
            if zone is None:
                continue
            mn, mx = zone
            x, z = p.pos.x, p.pos.z
            nx, nz = x, z
            if x < mn.x:
                nx = mn.x
            elif x > mx.x:
                nx = mx.x
            if z < mn.z:
                nz = mn.z
            elif z > mx.z:
                nz = mx.z
            if nx != x or nz != z:
                p.pos = Vec3(nx, p.pos.y, nz)
                # 消除「朝外」的速度分量（撞上無形邊界的行為）
                if nx != x and (p.vel.x > 0.0) == (nx > x):
                    p.vel = Vec3(0.0, p.vel.y, p.vel.z)
                if nz != z and (p.vel.z > 0.0) == (nz > z):
                    p.vel = Vec3(p.vel.x, p.vel.y, 0.0)

    def _rs_step(self, inputs: list[MoveInput | None], dt: float, movable: bool) -> None:
        """M4：Rust 世界迴圈（移動 + 碰撞一次跨邊界），其餘子系統仍 Python。"""
        n = len(self.players)
        fwd = [0.0] * n
        strafe = [0.0] * n
        walk = [False] * n
        crouch = [False] * n
        jump = [False] * n
        speed_mult = [1.0] * n
        alive = [False] * n
        for i, p in enumerate(self.players):
            inp = inputs[i] if i < len(inputs) else None
            if p.alive:
                alive[i] = True
                if inp is not None:
                    fwd[i] = inp.forward
                    strafe[i] = inp.strafe
                    walk[i] = inp.walk
                    crouch[i] = inp.crouch
                    jump[i] = inp.jump
                speed_mult[i] = p.status.move_speed_mult
        # 每 tick 先從 Python 同步狀態（重生/回彈/外部修改被尊重；Rust 是加速引擎）
        self._rs_world.sync_states(
            [(p.pos.x, p.pos.y, p.pos.z) for p in self.players],
            [(p.vel.x, p.vel.y, p.vel.z) for p in self.players])
        self._rs_world.step_all(fwd, strafe, walk, crouch, jump, speed_mult,
                                alive, dt, movable)
        # 回傳狀態寫回（移動/碰撞由 Rust 權威決定）
        for i, p in enumerate(self.players):
            px, py, pz = self._rs_world.positions()[i]
            vx, vy, vz = self._rs_world.velocities()[i]
            p.movement.pos = Vec3(px, py, pz)
            p.movement.vel = Vec3(vx, vy, vz)
            p.movement.on_ground = self._rs_world.on_grounds()[i]
            p.movement.crouching = self._rs_world.crouchings()[i]
            p.movement.walking = self._rs_world.walkings()[i]
            p.movement.time_since_land = self._rs_world.time_since_lands()[i]
            if p.alive:
                p.update(self.time, dt)

        # 實體彈道
        for proj in list(self.projectiles):
            ev = proj.step(dt, self.map_data)
            if ev == "detonate":
                self._detonate_projectile(proj)
            elif ev == "wall_bounce" and proj.behavior == "smoke":
                self._spawn_smoke(proj)
                self.projectiles.remove(proj)
        self.projectiles = [p for p in self.projectiles if p.pos is not None]

        # 部署物
        self.deployables = [t for t in self.deployables if not t.update(dt, self)]

        # 煙霧
        for s in self.smokes:
            s.update(dt)
        self.smokes = [s for s in self.smokes if s.active]

        if self.spike is not None:
            self.spike.update(dt)
        if self.match is not None:
            self.match.step(dt)

        self.tick += 1
        self.time = self.tick * dt

    # ------------------------------------------------------------------ #
    # 地圖互動機制（傳送門 / 繩索攀爬 / 可動鐵門）
    # ------------------------------------------------------------------ #
    def _update_teleporters(self, dt: float) -> None:
        """傳送門：冷卻遞減 + 入口範圍自動傳送。"""
        md = self.map_data
        # 冷卻遞減
        for slot in list(self._teleport_cooldowns):
            self._teleport_cooldowns[slot] = max(0.0, self._teleport_cooldowns[slot] - dt)
            if self._teleport_cooldowns[slot] <= 0:
                del self._teleport_cooldowns[slot]
        # 傳送門觸發
        if not hasattr(md, 'teleporters'):
            return
        for tp in md.teleporters:
            for slot, p in enumerate(self.players):
                if not p.alive:
                    continue
                if self._teleport_cooldowns.get(slot, 0) > 0:
                    continue
                if tp.team_restricted >= 0 and p.team != tp.team_restricted:
                    continue
                if p.pos.distance_to(tp.entrance) <= tp.radius:
                    p.pos = Vec3(tp.exit.x, tp.exit.y, tp.exit.z)
                    p.vel = Vec3()
                    self._teleport_cooldowns[slot] = tp.cooldown
                    self.event_log.append(f"teleport: slot{slot} {tp.entrance} -> {tp.exit}")

    def _update_ropes(self, dt: float) -> None:
        """繩索攀爬進度更新：沿繩索勻速移動。"""
        md = self.map_data
        if not hasattr(md, 'ropes'):
            return
        for slot in list(self._rope_active):
            rope_idx = self._rope_active[slot]
            if rope_idx < 0 or rope_idx >= len(md.ropes):
                del self._rope_active[slot]
                self._rope_progress.pop(slot, None)
                continue
            rope = md.ropes[rope_idx]
            progress = self._rope_progress.get(slot, 0.0)
            rope_len = rope.start.distance_to(rope.end)
            if rope_len > 0.01:
                progress += dt * rope.speed / rope_len
            if progress >= 1.0:
                p = self.players[slot]
                p.pos = Vec3(rope.end.x, rope.end.y, rope.end.z)
                p.vel = Vec3()
                del self._rope_active[slot]
                self._rope_progress.pop(slot, None)
                self.event_log.append(f"rope_arrive: slot{slot} at {rope.end}")
            else:
                p = self.players[slot]
                p.pos = rope.start + (rope.end - rope.start) * progress
                p.vel = Vec3()  # 攀爬中無水平速度
                self._rope_progress[slot] = progress

    def interact(self, slot: int) -> bool:
        """F 鍵互動：尋找最近的繩索/鐵門並觸發。
        回傳 True 表示有互動成功。"""
        p = self.players[slot]
        if not p.alive:
            return False
        md = self.map_data

        # ── 繩索攀爬：靠近起點 → 開始攀爬 ──
        if hasattr(md, 'ropes'):
            for i, rope in enumerate(md.ropes):
                if p.pos.distance_to(rope.start) <= rope.radius:
                    if self._rope_active.get(slot, -1) == i:
                        return False  # 已在攀爬
                    self._rope_active[slot] = i
                    self._rope_progress[slot] = 0.0
                    self.event_log.append(f"rope_start: slot{slot} on rope{i}")
                    return True
                # 雙向：靠近終點也可以開始
                if rope.bidirectional and p.pos.distance_to(rope.end) <= rope.radius:
                    if self._rope_active.get(slot, -1) == i:
                        return False
                    self._rope_active[slot] = i
                    self._rope_progress[slot] = 0.0
                    # 反向攀爬：交換 start/end
                    self.event_log.append(f"rope_start: slot{slot} on rope{i} (reverse)")
                    return True

        # ── 可動鐵門：靠近開關 → 切換狀態 ──
        if hasattr(md, 'doors'):
            for door in md.doors:
                if p.pos.distance_to(door.toggle_pos) <= door.toggle_radius:
                    door.open = not door.open
                    if door.open:
                        # 開啟：從牆面列表移除
                        if door.wall in md.walls:
                            md.walls.remove(door.wall)
                            md._ray_hash = None  # 清除射線快取
                        # 清除碰撞空間雜湊
                        if hasattr(self, '_wall_hash'):
                            self._wall_hash = None
                    else:
                        # 關閉：加入牆面列表
                        if door.wall not in md.walls:
                            md.walls.append(door.wall)
                            md._ray_hash = None
                        if hasattr(self, '_wall_hash'):
                            self._wall_hash = None
                    self.event_log.append(f"door_toggle: slot{slot} {door.door_name} -> {'open' if door.open else 'closed'}")
                    return True

        return False

    # ------------------------------------------------------------------ #
    # 射擊（伺服器權威，含 Rollback 目標位置注入）
    # ------------------------------------------------------------------ #
    def fire_shot(self, slot: int, yaw_deg: float, pitch_deg: float,
                  target_positions: dict[int, Vec3] | None = None) -> list:
        p = self.players[slot]
        if not p.alive or not p.status.can_shoot:
            return []
        if p.inventory.switching(self.time):          # 切槍期間不可開火
            return []
        if not p.weapon.attempt_fire(self.time):
            return []
        stats = p.weapon.stats
        aim_yaw = yaw_deg + p.weapon.aim_yaw_offset
        aim_pitch = pitch_deg + p.weapon.aim_pitch_offset
        forward = dir_from_yaw_pitch(aim_yaw, aim_pitch)
        me_deg = _MOVEMENT_ERROR.error_for(p.movement, stats.wclass)
        spread = self.spread_engine.spread_deg(
            stats, me_deg, max(0, p.weapon.recoil.bullet_index - 1),
            not p.movement.on_ground, p.movement.ads, p.movement.crouching,
        )
        origin = p.pos + Vec3(0, EYE_HEIGHT, 0)
        all_hits = []
        for _ in range(stats.pellets):
            d = self.spread_engine.sample_dir(forward, spread)
            res = resolve_hitscan(self, self.map_data, slot, origin, d, stats, target_positions)
            all_hits.extend(res.hits)
        # 近戰背刺：刀從背後命中 → 一擊倒（特戰式）
        if stats.key == "knife" and all_hits:
            for h in all_hits:
                victim = self.players[h.target_slot]
                if not victim.alive:
                    continue
                # 目標是否背對射手：射手前向 vs 射手→目標方向
                to_victim = victim.pos - p.pos
                to_victim.y = 0.0
                if to_victim.length_sq() < 0.01:
                    continue
                to_victim = to_victim.normalized()
                # 目標的朝向（從其 vel 推斷，或從其相對射手的位置）
                victim_fwd = victim.vel.horizontal()
                if victim_fwd.length_sq() > 0.01:
                    victim_fwd = victim_fwd.normalized()
                    # 目標正在遠離射手（背對）→ 背刺
                    if victim_fwd.dot(to_victim) > 0.3:
                        victim.apply_damage(999.0, source_slot=slot, weapon_key="knife_backstab")
        return all_hits

    # ------------------------------------------------------------------ #
    # 技能與實體
    # ------------------------------------------------------------------ #
    def cast_ability(self, slot: int, index: int, yaw_deg: float, pitch_deg: float) -> bool:
        p = self.players[slot]
        if not p.alive:
            return False
        aim = dir_from_yaw_pitch(yaw_deg, pitch_deg)
        return p.abilities.cast(index, self, slot, aim)

    def spawn_projectile(self, proj: Projectile) -> None:
        self.projectiles.append(proj)

    def _detonate_projectile(self, proj: Projectile) -> None:
        if proj.behavior == "frag":
            explode(self, self.map_data, proj.pos, proj.explosion_radius, proj.damage,
                    team=proj.team, ignore_los=False, source_slot=proj.owner_slot)
        elif proj.behavior == "flash":
            radius = proj.params.get("radius", 8.0)
            duration = proj.params.get("duration", 2.0)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= radius:
                    if self.map_data.los_clear(proj.pos, p.pos + Vec3(0, 1.0, 0)):
                        p.status.apply("blind", duration, 1.0)
        elif proj.behavior == "smoke":
            self._spawn_smoke(proj)
        elif proj.behavior == "line_hit":
            # 線性投射物命中爆炸：小範圍傷害
            dmg = proj.params.get("damage", proj.damage)
            r = proj.params.get("radius", 0.5)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r + 0.5:
                    p.apply_damage(dmg, source_slot=proj.owner_slot, weapon_key="line_hit")
        elif proj.behavior == "slow_orb":
            # 減速球：落地後生成減速區域
            r = proj.params.get("radius", 4.0)
            dur = proj.params.get("duration", 5.0)
            pot = proj.params.get("potency", 1.0)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r:
                    p.status.apply(SLOW, dur, pot)
        elif proj.behavior == "nearsight":
            # 近視彈：範圍內敵方被近視+聽覺封鎖
            r = proj.params.get("radius", 3.0)
            ns_dur = proj.params.get("ns_duration", 3.0)
            df_dur = proj.params.get("deafen_duration", 1.5)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r:
                    if self.map_data.los_clear(proj.pos, p.pos + Vec3(0, 1.0, 0)):
                        p.status.apply(NEARSIGHT, ns_dur, 1.0)
                        p.status.apply(DEAFENED, df_dur, 1.0)
        elif proj.behavior == "suppress":
            # 技能封鎖範圍
            r = proj.params.get("radius", 8.0)
            dur = proj.params.get("duration", 3.0)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r:
                    p.status.apply(SUPPRESSED, dur, 1.0)
        elif proj.behavior == "recon":
            # 偵查箭：範圍內敵方被 REVEALED
            r = proj.params.get("radius", 6.0)
            dur = proj.params.get("duration", 2.0)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r:
                    p.status.apply(REVEALED, dur, 1.0)
        elif proj.behavior == "drone":
            # 無人機：範圍內敵方被 REVEALED
            r = proj.params.get("radius", 4.0)
            dur = proj.params.get("duration", 2.0)
            for slot, p in enumerate(self.players):
                if not p.alive or p.team == proj.team:
                    continue
                if p.pos.distance_to(proj.pos) <= r:
                    p.status.apply(REVEALED, dur, 1.0)
        elif proj.behavior == "flame":
            # 火焰區域：生成持續傷害區
            r = proj.params.get("radius", 3.0)
            dmg = proj.params.get("damage", 40.0)
            dur = proj.params.get("duration", 6.0)
            # 在落地點生成火焰 deployable
            flame = _FlameZone(proj.pos, proj.team, r, dmg, dur)
            self.deployables.append(flame)
        elif proj.behavior == "fake_footstep":
            # 假腳步聲：無效果，僅消耗
            pass
        self.projectiles.remove(proj)

    def _spawn_smoke(self, proj: Projectile) -> None:
        self.smokes.append(
            SmokeCloud(proj.pos, proj.params.get("radius", 3.5),
                       proj.params.get("duration", 15.0), self.rng)
        )

    # ------------------------------------------------------------------ #
    def _on_player_killed(self, victim_slot: int, killer_slot: int, weapon_key: str) -> None:
        best = -1
        if 0 <= killer_slot < len(self.players) and killer_slot != victim_slot:
            k = self.players[killer_slot]
            k.kills += 1
            k.economy.grant(KILL_REWARD)
            # 助攻：同隊（兇手隊）中對受害者傷害最高、≥25 且非兇手者 +1
            victim = self.players[victim_slot]
            best, best_dmg = -1, 25.0
            for atk, dmg in victim.dmg_log.items():
                if atk == killer_slot or not (0 <= atk < len(self.players)):
                    continue
                if self.players[atk].team != k.team:
                    continue
                if dmg > best_dmg:
                    best, best_dmg = atk, dmg
            if best >= 0:
                self.players[best].assists += 1
                self.event_log.append(f"assist: slot{best} on slot{victim_slot} (killer slot{killer_slot})")
        self.event_log.append(f"kill: slot{victim_slot} by slot{killer_slot} ({weapon_key})")
        # 每日任務：kill/assist 累進
        try:
            if 0 <= killer_slot < len(self.players):
                self._get_mission(killer_slot).record("kill")
                self._get_mission(killer_slot).record("damage", int(self.players[victim_slot].dmg_log.get(killer_slot, 0)))
            if best >= 0:
                self._get_mission(best).record("assist")
        except Exception:
            pass
        # 死鬥 / 團隊死鬥：記錄擊殺 + 設定復活計時
        if self.match is not None and self.match.mode in ("deathmatch", "teamdeathmatch"):
            if 0 <= killer_slot < len(self.match.dm_kill_counts):
                self.match.dm_kill_counts[killer_slot] += 1
            if self.match.mode == "teamdeathmatch" and 0 <= killer_slot < len(self.players):
                self.match.tdm_team_kills[self.players[killer_slot].team] += 1
                try:
                    from server.game.modes import tdm_next_weapon
                    k = self.players[killer_slot]
                    nk = tdm_next_weapon(k.kills)
                    if nk != k.inventory.active_state().stats.key:
                        k.grant_weapon(nk)
                        self.event_log.append(f"tdm_upgrade: slot{killer_slot} -> {nk} ({k.kills} kills)")
                except Exception:
                    pass
            if 0 <= victim_slot < len(self.match.dm_respawn_timers):
                self.match.dm_respawn_timers[victim_slot] = 2.0 if self.match.mode == "teamdeathmatch" else 3.0

    def los_blocked_by_smoke(self, a: Vec3, b: Vec3) -> bool:
        """a→b 視線是否被任一煙霧球擋住（M11）。"""
        return any(s.blocks_segment(a, b) for s in self.smokes)

    def states(self) -> list:
        return [
            PlayerMoveState(
                slot=i, pos=p.pos, vel=p.vel, on_ground=p.on_ground,
                crouching=p.crouching, walking=p.walking,
            )
            for i, p in enumerate(self.players)
        ]

    def position(self, slot: int) -> Vec3:
        return self.players[slot].pos


# ---------------------------------------------------------------------- #
# 火焰區域（Brimstone Incendiary / Phoenix Blaze）
# ---------------------------------------------------------------------- #
class _FlameZone:
    """地面火焰區域：範圍內敵方持續扣血。"""

    def __init__(self, pos: Vec3, team: int, radius: float, dmg_per_sec: float, duration: float):
        self.pos = pos
        self.team = team
        self.radius = radius
        self.dmg_per_sec = dmg_per_sec
        self.time_left = duration
        self.triggered = False

    def update(self, dt: float, world) -> bool:
        self.time_left -= dt
        if self.time_left <= 0.0:
            return True
        for slot, p in enumerate(world.players):
            if not p.alive or p.team == self.team:
                continue
            if p.pos.distance_to(self.pos) <= self.radius:
                dmg = self.dmg_per_sec * dt
                p.apply_damage(dmg, source_slot=-1, weapon_key="flame")
        return False
