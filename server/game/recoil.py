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
    """取用順序：每把槍的專屬指紋 → 依類別退回（未知武器仍能玩）。"""
    own = PATTERNS.get(stats.key)
    if own is not None and own.key == stats.key:
        return own
    if stats.wclass == "smg":
        return PATTERNS["smg"]
    if stats.wclass == "sidearm":
        return PATTERNS["sidearm"]
    if not stats.automatic or stats.burst > 1:
        return PATTERNS["semi"]
    return PATTERNS["default"]


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
        """目前累積的準線偏移（度）——「恢復」已經反映在這裡。"""
        return self.pitch, self.yaw

    def reset_pattern(self) -> None:
        """重新開始图案（換彈後回到第 1 發）：連發的「第 1 發最準」必須能再次拿到。"""
        self.bullet_index = 0

    def fully_recovered(self) -> bool:
        return abs(self.pitch) < 1e-9 and abs(self.yaw) < 1e-9




# --------------------------------------------------------------------------- #
# 每把槍的「專屬指紋」（PATTERNS 的 key 直接就是武器 key → pattern_for 優先取用）
# ------------------------------------------------------------------------- #
# 「練槍」的樂趣在於每把槍有自己的個性，因此 class 图案只當退回用（未知武器/測試）：
#   * pitch 前幾發最猛、之後遞減成平台（不會無限上升）
#   * yaw 前幾發為 0（= 保護彈，可完全控槍的彈數），之後才擺動
#   * 射速高 → 單發小但累積快、保護彈多；射速低 → 單發大、恢復快
#   * reset_time/recover_rate 決定「停火多久回到原點」（點射流派的命脈）
# --------------------------------------------------------------------------- #
_PER_WEAPON: list[RecoilPattern] = [
    # 步槍：Vandal / Phantom 的圖案即上方「保護彈」規則的教科書範例
    RecoilPattern("vandal",
        (1.1, 2.0, 2.7, 2.4, 2.0, 1.5, 1.1, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.35, 0.3, 0.3,
         0.3, 0.25, 0.25, 0.2),
        (0.0, 0.0, 0.0, 0.35, 0.55, 0.25, -0.45, -0.65, -0.3, 0.5, 0.85, 0.4, -0.6, -0.9,
         0.2, 0.6, 0.3, -0.5, 0.4, 0.2),
        protected_bullets=6, reset_time=0.7, recover_rate=6.0),
    RecoilPattern("phantom",
        (0.9, 1.7, 2.2, 2.0, 1.7, 1.3, 1.0, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.35, 0.3, 0.3,
         0.25, 0.25, 0.2, 0.2),
        (0.0, 0.0, 0.0, 0.2, 0.4, 0.3, 0.1, -0.3, -0.5, -0.2, 0.4, 0.6, 0.3, -0.4, -0.6,
         -0.1, 0.4, 0.3, -0.3, 0.2),
        protected_bullets=8, reset_time=0.7, recover_rate=6.0),
    RecoilPattern("guardian",     # 半自動：單發乾淨、恢復極快，但彈匣小
        (1.5, 1.1, 0.9),
        (0.0, 0.15, -0.2),
        protected_bullets=1, reset_time=0.35, recover_rate=11.0),
    RecoilPattern("bulldog",      # 三連發：第 2 發最猛，最後一發往右飄
        (1.2, 1.8, 1.5, 0.9, 0.6),
        (0.0, 0.1, 0.5, 0.2, -0.3),
        protected_bullets=3, reset_time=0.45, recover_rate=8.5),
    # --- 衝鋒槍（smg）：高射速 → 累積快、保護彈多 ---
    RecoilPattern("spectre",
        (0.5, 0.9, 1.2, 1.35, 1.3, 1.15, 1.0, 0.9, 0.8, 0.72, 0.66, 0.6, 0.56, 0.52, 0.5,
         0.48, 0.46, 0.45),
        (0.0, 0.0, 0.15, 0.3, 0.2, -0.25, -0.4, -0.2, 0.35, 0.5, 0.25, -0.3, -0.45, 0.15,
         0.4, -0.2, 0.1, -0.15),
        protected_bullets=7, reset_time=0.55, recover_rate=8.0),
    RecoilPattern("stinger",      # 四連發：起手略跳，尾彈收斂
        (0.7, 1.1, 1.3, 1.0, 0.7, 0.5),
        (0.0, 0.0, 0.25, 0.45, -0.2, -0.35),
        protected_bullets=4, reset_time=0.5, recover_rate=8.5),
    # --- 手槍（sidearm）---
    RecoilPattern("classic",      # 三連發手槍：第一發極準，連發才飄
        (0.55, 0.95, 0.8, 0.5),
        (0.0, 0.0, 0.3, -0.25),
        protected_bullets=3, reset_time=0.4, recover_rate=9.5),
    RecoilPattern("ghost",        # 資料表為全自動手槍：扣著不放會往上輕爬，第 4 發見頂
        (0.85, 1.25, 1.5, 1.55, 1.45, 1.3, 1.15, 1.0),
        (0.0, 0.15, -0.2, 0.3, 0.45, -0.25, -0.45, 0.2),
        protected_bullets=2, reset_time=0.45, recover_rate=9.5),
    RecoilPattern("sheriff",      # 一發重砲：大跳、大恢復
        (2.4, 1.4, 0.9),
        (0.0, 0.35, -0.5),
        protected_bullets=1, reset_time=0.35, recover_rate=13.0),
    RecoilPattern("frenzy",       # 全自動手槍：射速最高，累積明顯
        (0.4, 0.7, 0.9, 1.0, 0.95, 0.85, 0.75, 0.66, 0.6, 0.55, 0.5),
        (0.0, 0.0, 0.25, 0.5, 0.3, -0.3, -0.55, -0.25, 0.4, 0.2, -0.2),
        protected_bullets=4, reset_time=0.5, recover_rate=8.0),
    RecoilPattern("bandit",       # 半自動：準度好、後座小
        (1.0, 0.7),
        (0.0, 0.2),
        protected_bullets=1, reset_time=0.35, recover_rate=10.5),
    RecoilPattern("shorty",       # 散彈手槍：一發就需重新瞄
        (1.7, 1.2),
        (0.0, 0.4),
        protected_bullets=1, reset_time=0.4, recover_rate=9.0),
    # --- 霰彈（shotgun）：单發巨大、恢復快（反正要打近距離）---
    RecoilPattern("bucky",
        (3.0, 2.2, 1.6, 1.2, 1.0),
        (0.0, 0.3, -0.4, 0.2, 0.1),
        protected_bullets=1, reset_time=0.4, recover_rate=7.5),
    RecoilPattern("judge",        # 全自動霰彈：連發時往上鉤
        (2.5, 2.1, 1.9, 1.7, 1.5, 1.35, 1.2, 1.1),
        (0.0, 0.25, 0.5, 0.2, -0.35, -0.5, -0.2, 0.3),
        protected_bullets=2, reset_time=0.5, recover_rate=7.0),
    # --- 狙擊（sniper）：一發入魂，開完必須重新找點 ---
    RecoilPattern("operator",
        (4.2, 2.4),
        (0.0, 0.6),
        protected_bullets=1, reset_time=0.5, recover_rate=5.5),
    RecoilPattern("outlaw",       # 雙管：第二發仍很跳
        (3.1, 2.3, 1.2),
        (0.0, 0.45, 0.2),
        protected_bullets=1, reset_time=0.45, recover_rate=7.0),
    RecoilPattern("marshal",      # 輕狙：比 Operator 可控
        (2.3, 1.5, 0.9),
        (0.0, 0.3, 0.15),
        protected_bullets=1, reset_time=0.4, recover_rate=8.5),
    # --- 重型（heavy）：全彈匣掃射，個性在最長的尾巴上 ---
    RecoilPattern("ares",         # 50 發：往右漂移 + 慢恢復（壓制用）
        (0.5, 0.85, 1.1, 1.25, 1.3, 1.32, 1.3, 1.26, 1.22, 1.2, 1.18, 1.16, 1.15, 1.14,
         1.13, 1.12, 1.12, 1.11, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1),
        (0.0, 0.0, 0.3, 0.55, 0.75, 0.95, 1.1, 1.2, 1.25, 1.3, 1.2, 1.05, 0.9, 0.75, 0.6,
         0.45, 0.3, 0.15, 0.0, -0.2, -0.4, -0.55, -0.7, -0.5, -0.3, -0.1, 0.15, 0.35, 0.5,
         0.65),
        protected_bullets=4, reset_time=1.1, recover_rate=3.4, random_yaw_scale=1.15),
    RecoilPattern("odin",         # 100 發：垂直爬升更高、左右較收斂
        (0.6, 1.0, 1.3, 1.55, 1.7, 1.78, 1.8, 1.78, 1.75, 1.72, 1.7, 1.68, 1.66, 1.65,
         1.64, 1.63, 1.62, 1.62, 1.61, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6,
         1.6),
        (0.0, 0.0, 0.2, 0.4, 0.3, -0.25, -0.45, -0.2, 0.35, 0.5, 0.25, -0.3, -0.4, -0.15,
         0.2, 0.4, 0.15, -0.25, -0.35, 0.1, 0.3, 0.05, -0.2, -0.3, 0.15, 0.25, -0.1,
         -0.2, 0.1, 0.2),
        protected_bullets=8, reset_time=1.2, recover_rate=3.0, random_yaw_scale=0.85),
]
for _p in _PER_WEAPON:
    _reg(_p)     # 同名覆蓋 class 图案（vandal/phantom 沿用同一組數字）


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
