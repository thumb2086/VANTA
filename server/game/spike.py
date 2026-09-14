"""
server/game/spike.py — M9 Spike 目標機制
========================================
  * 安放：4 秒（需站於點位內、期間不可移動/死亡，否則中斷）
  * 拆除：7 秒，3.5 秒設檢查點（過半後可離開再回來繼續）
  * 爆炸：安放後 45 秒倒數；倒數歸零 → 範圍致死判定（攻方獲勝）
  * 安放完成：攻方全員 +300（經濟，見 economy.py）
"""

from __future__ import annotations

from enum import Enum

from server.core.math_core import Vec3
from server.game.economy import SPIKE_PLANT_REWARD

PLANT_TIME = 4.0
DEFUSE_TIME = 7.0
HALF_DEFUSE_CHECKPOINT = DEFUSE_TIME / 2.0
FUSE_TIME = 45.0
EXPLOSION_RADIUS = 25.0
EXPLOSION_DAMAGE = 150.0
PLANT_RADIUS = 2.5


class SpikeState(Enum):
    IDLE = "idle"
    PLANTING = "planting"
    PLANTED = "planted"
    DEFUSING = "defusing"
    DETONATED = "detonated"
    DEFUSED = "defused"


class SpikeController:
    def __init__(self, world, map_data):
        self.world = world
        self.map_data = map_data
        self.state = SpikeState.IDLE
        self.plant_progress = 0.0
        self.defuse_progress = 0.0
        self.fuse = FUSE_TIME
        self.site = None
        self.planter_slot: int | None = None
        self.attacker_team: int = 0
        self.defuser_slot: int | None = None
        self.holding_defuse = False

    # ------------------------------------------------------------------ #
    # 輸入（伺服器權威，由 ACTION 封包觸發）
    # ------------------------------------------------------------------ #
    def try_begin_plant(self, slot: int) -> bool:
        p = self.world.players[slot]
        if self.state != SpikeState.IDLE or not p.alive:
            return False
        site = self._site_under(p.pos)
        if site is None:
            return False
        self.state = SpikeState.PLANTING
        self.planter_slot = slot
        self.attacker_team = p.team
        self.site = site
        self.plant_progress = 0.0
        return True

    def cancel_plant(self) -> None:
        if self.state == SpikeState.PLANTING:
            self.state = SpikeState.IDLE
            self.planter_slot = None
            self.plant_progress = 0.0

    def set_hold_plant(self, slot: int, hold: bool) -> None:
        if hold:
            self.try_begin_plant(slot)
        else:
            if self.state == SpikeState.PLANTING and self.planter_slot == slot:
                self.cancel_plant()

    def try_begin_defuse(self, slot: int) -> bool:
        p = self.world.players[slot]
        if self.state != SpikeState.PLANTED or not p.alive:
            return False
        if p.pos.distance_to(self._spike_pos()) > 2.0:
            return False
        self.state = SpikeState.DEFUSING
        self.defuser_slot = slot
        self.holding_defuse = True
        return True

    def set_hold_defuse(self, slot: int, hold: bool) -> None:
        self.holding_defuse = hold
        if hold:
            self.try_begin_defuse(slot)
        else:
            if self.state == SpikeState.DEFUSING and self.defuser_slot == slot:
                # 過半檢查點：>=3.5s 記錄，下次可續拆
                if self.defuse_progress < HALF_DEFUSE_CHECKPOINT:
                    self.defuse_progress = 0.0
                self.state = SpikeState.PLANTED
                self.defuser_slot = None

    # ------------------------------------------------------------------ #
    # 每 tick 更新
    # ------------------------------------------------------------------ #
    def update(self, dt: float) -> None:
        if self.state == SpikeState.PLANTING:
            planter = self.world.players[self.planter_slot]
            valid = (
                planter.alive
                and planter.vel.horizontal().length() < 0.2       # 安放期間不可移動
                and self._site_under(planter.pos) is not None
            )
            if not valid:
                self.cancel_plant()
                return
            self.plant_progress += dt
            if self.plant_progress >= PLANT_TIME:
                self.state = SpikeState.PLANTED
                self.fuse = FUSE_TIME
                # 攻方全員 +300（含計畫手；不含已死亡）
                attacker_team = planter.team
                for pl in self.world.players:
                    if pl.team == attacker_team and pl.alive:
                        pl.economy.grant(SPIKE_PLANT_REWARD)

        elif self.state == SpikeState.PLANTED:
            self.fuse -= dt
            if self.fuse <= 0.0:
                self.state = SpikeState.DETONATED
                # 範圍致死判定（核爆：無視牆壁，近似《特戰英豪》）
                from server.game.ballistics import explode

                # 範圍致死：半徑內全傷，但攻方（爆炸即勝）不受傷
                explode(
                    self.world, self.map_data,
                    center=self._spike_pos(), radius=EXPLOSION_RADIUS,
                    damage=EXPLOSION_DAMAGE, team=self.attacker_team,
                    ignore_los=True, weapon_key="spike", flat=True,
                )

        elif self.state == SpikeState.DEFUSING:
            defuser = self.world.players[self.defuser_slot]
            valid = (
                defuser.alive
                and self.holding_defuse
                and defuser.pos.distance_to(self._spike_pos()) <= 2.0
            )
            if not valid:
                self.set_hold_defuse(self.defuser_slot, False)
                return
            self.defuse_progress += dt
            if self.defuse_progress >= DEFUSE_TIME:
                self.state = SpikeState.DEFUSED

    # ------------------------------------------------------------------ #
    def _spike_pos(self) -> Vec3:
        if self.site is not None:
            return self.site.center + Vec3(0, 0.5, 0)
        return Vec3()

    def _site_under(self, pos: Vec3):
        for s in self.map_data.sites:
            if pos.distance_to(s.center) <= s.radius:
                return s
        return None

    def reset(self) -> None:
        self.state = SpikeState.IDLE
        self.plant_progress = 0.0
        self.defuse_progress = 0.0
        self.fuse = FUSE_TIME
        self.site = None
        self.planter_slot = None
        self.attacker_team = 0
        self.defuser_slot = None
        self.holding_defuse = False

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "plant_progress": self.plant_progress,
            "defuse_progress": self.defuse_progress,
            "fuse": self.fuse,
            "site": self.site.name if self.site else None,
        }
