"""
server/game/recoil.py — M5 後座力與擴散引擎
===========================================
  * 固定後座力圖案 (RecoilPattern)：陣列式，前 N 發「保護彈」完全確定，
    之後 yaw 加入隨機偏移（與《特戰英豪》「前幾發固定、之後機率性左右擺動」一致）。
  * 後座恢復：停火超過 reset_time 後以 recover_rate 線性回復至原點；
    未完全恢復就開火 → 殘餘後座疊加（連射懲罰）。
  * 隨機擴散圓 (Spread Cone)：首發（靜止）幾乎精準，之後每發成長，
    加上移動誤差（M1 引擎輸出），ADS 減半，落地懲罰來自 M1。
"""

from __future__ import annotations

import math

from dataclasses import dataclass

from server.core.math_core import Vec3, clamp, deg2rad
from server.game.weapons import WeaponStats


@dataclass(frozen=True, slots=True)
class RecoilPattern:
    key: str
    pitch_deg: tuple[float, ...]      # 每發垂直偏移（正值向上）
    yaw_deg: tuple[float, ...]        # 每發水平偏移（正值向右）
    protected_bullets: int            # 完全確定的彈數（之後 yaw 隨機）
    reset_time: float                 # 停火多久後開始恢復（秒）
    recover_rate: float               # 恢復速度（度/秒）
    random_yaw_scale: float = 0.6     # 保護彈之後的隨機 yaw 振幅（度）


PATTERNS: dict[str, RecoilPattern] = {}


def _reg(p: RecoilPattern) -> None:
    PATTERNS[p.key] = p


# 近似圖案：垂直先快後緩，水平小擺動；Vandal 6 顆保護、Phantom 8 顆
_reg(RecoilPattern("vandal",
    (1.1, 2.0, 2.7, 2.4, 2.0, 1.5, 1.1, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.35, 0.3, 0.3, 0.3, 0.25, 0.25, 0.2),
    (0.0, 0.0, 0.0, 0.35, 0.55, 0.25, -0.45, -0.65, -0.3, 0.5, 0.85, 0.4, -0.6, -0.9, 0.2, 0.6, 0.3, -0.5, 0.4, 0.2),
    protected_bullets=6, reset_time=0.7, recover_rate=6.0))
_reg(RecoilPattern("phantom",
    (0.9, 1.7, 2.2, 2.0, 1.7, 1.3, 1.0, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.35, 0.3, 0.3, 0.25, 0.25, 0.2, 0.2),
    (0.0, 0.0, 0.0, 0.2, 0.4, 0.3, 0.1, -0.3, -0.5, -0.2, 0.4, 0.6, 0.3, -0.4, -0.6, -0.1, 0.4, 0.3, -0.3, 0.2),
    protected_bullets=8, reset_time=0.7, recover_rate=6.0))
_reg(RecoilPattern("smg",
    (0.8, 1.4, 1.8, 1.6, 1.3, 1.0, 0.8, 0.7, 0.6, 0.5, 0.45, 0.4, 0.35, 0.3, 0.3, 0.25),
    (0.0, 0.0, 0.2, 0.4, 0.3, -0.3, -0.5, -0.2, 0.3, 0.5, 0.2, -0.4, -0.3, 0.3, 0.2, -0.2),
    protected_bullets=6, reset_time=0.6, recover_rate=8.0))
_reg(RecoilPattern("sidearm",
    (0.8, 1.2, 1.0, 0.8, 0.6),
    (0.0, 0.2, 0.0, -0.2, 0.0),
    protected_bullets=5, reset_time=0.5, recover_rate=9.0))
_reg(RecoilPattern("semi",
    (1.0,), (0.0,), protected_bullets=1, reset_time=0.4, recover_rate=10.0))
_reg(RecoilPattern("default",
    (1.0, 1.5, 1.8, 1.6, 1.4, 1.2, 1.0, 0.8),
    (0.0, 0.0, 0.2, 0.3, 0.1, -0.3, -0.4, 0.2),
    protected_bullets=4, reset_time=0.7, recover_rate=6.0))


def pattern_for(stats: WeaponStats) -> RecoilPattern:
    if stats.wclass == "smg":
        return PATTERNS["smg"]
    if stats.wclass == "sidearm":
        return PATTERNS["sidearm"]
    if not stats.automatic or stats.burst > 1:
        return PATTERNS["semi"]
    key = stats.key if stats.key in PATTERNS else "default"
    return PATTERNS[key]


class RecoilController:
    """單一武器的後座力狀態：每發偏移累積 + 恢復。"""

    def __init__(self, pattern: RecoilPattern, rng):
        self.pattern = pattern
        self.rng = rng
        self.bullet_index = 0
        self.pitch = 0.0          # 目前累積垂直偏移（度）
        self.yaw = 0.0            # 目前累積水平偏移（度）
        self.last_fire_time = -1e9
        self.shots_fired = 0

    def fire(self, now: float) -> tuple[float, float]:
        """開火：回傳 (pitch增量, yaw增量)，並更新內部狀態。"""
        i = self.bullet_index
        p = self.pattern.pitch_deg[min(i, len(self.pattern.pitch_deg) - 1)]
        if i < len(self.pattern.yaw_deg) and i < self.pattern.protected_bullets:
            y = self.pattern.yaw_deg[i]
        else:
            # 保護彈之後：固定模式帶隨機 yaw 擺動（機率性偏移）
            y = (self.pattern.yaw_deg[min(i, len(self.pattern.yaw_deg) - 1)] if
                 self.pattern.yaw_deg else 0.0) + self.rng.uniform(
                -self.pattern.random_yaw_scale, self.pattern.random_yaw_scale)
        self.bullet_index += 1
        self.shots_fired += 1
        self.last_fire_time = now
        self.pitch += p
        self.yaw += y
        return p, y

    def update(self, now: float, dt: float) -> None:
        """每 tick 更新：停火超過 reset_time 後開始恢復（步進式，落在 0 上不震盪）。"""
        if now - self.last_fire_time > self.pattern.reset_time:
            step = self.pattern.recover_rate * dt
            if abs(self.pitch) <= step:
                self.pitch = 0.0
            else:
                self.pitch = clamp(self.pitch - math.copysign(step, self.pitch), -90.0, 90.0)
            if abs(self.yaw) <= step:
                self.yaw = 0.0
            else:
                self.yaw = clamp(self.yaw - math.copysign(step, self.yaw), -90.0, 90.0)

    def current_offset(self) -> tuple[float, float]:
        return self.pitch, self.yaw

    def fully_recovered(self) -> bool:
        return abs(self.pitch) < 1e-9 and abs(self.yaw) < 1e-9


class SpreadEngine:
    """計算「該槍 + 該狀態」的擴散半角（度），並採樣方向。"""

    def __init__(self, rng):
        self.rng = rng

    def spread_deg(
        self,
        stats: WeaponStats,
        movement_error_deg: float,
        bullet_index: int,
        airborne: bool,
        is_ads: bool,
        crouching: bool,
    ) -> float:
        base = stats.first_shot_accuracy
        growth = min(bullet_index, 8) * stats.spread_per_bullet
        mv = movement_error_deg
        if is_ads:
            mv *= stats.ads_spread_mult
        if crouching and not airborne:
            mv *= 0.7
        return base + growth + mv

    def sample_dir(self, forward: Vec3, spread_deg: float) -> Vec3:
        """在擴散圓錐內採樣方向（均勻圓盤投影）。"""
        if spread_deg <= 1e-6:
            return forward
        up = Vec3(0.0, 1.0, 0.0)
        right = forward.cross(up)
        if right.length() < 1e-6:
            right = Vec3(1.0, 0.0, 0.0)
        right = right.normalized()
        up2 = right.cross(forward).normalized()
        theta = self.rng.uniform(0.0, math.tau)
        r = math.sqrt(self.rng.random()) * math.tan(deg2rad(spread_deg))
        offset = right * (math.cos(theta) * r) + up2 * (math.sin(theta) * r)
        d = forward + offset
        return d.normalized()
