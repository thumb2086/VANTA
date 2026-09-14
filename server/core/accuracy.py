"""
server/core/accuracy.py — 移動精準度懲罰 (Movement Penalty)
===========================================================
《特戰英豪》「移動速度 ↔ 射擊精準度」動態關聯模型（社群量測近似，皆可調）：

  * 靜止站立        → 無懲罰 (0)
  * 跑步 (跑速 100%) → 該武器類別最大誤差 (100%)
  * 靜步 (Shift)     → 約最大誤差 × 0.50
  * 蹲走 (Crouch)    → 約最大誤差 × 0.35（比靜步更小，鼓勵蹲射）
  * 空中            → 約最大誤差 × 1.25（比跑步更糟）
  * 落地            → 額外 +7°，持續 0.225s，線性衰減（落地急停後不能立刻滿準）

回傳值單位：度 (degrees)，將作為「擴散圓半徑」疊加至射擊引擎（見 M5）。
實作時注意：懲罰只與「位移速度」掛鉤；被緩速/加速的狀態（如技能）不應
影響此數值（與真實遊戲一致）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.core.math_core import clamp

# 各武器類別的「最大移動誤差」（度）。此為近似值，M5 武器資料庫完成後以
# 每把武器的 first_shot_accuracy 為準進行細調。
DEFAULT_MAX_ERROR_DEG: dict[str, float] = {
    "sidearm": 0.3,
    "smg": 1.2,
    "rifle": 2.4,
    "sniper": 3.0,
    "shotgun": 1.8,
    "heavy": 2.0,
}


@dataclass(frozen=True, slots=True)
class AccuracyConfig:
    max_error_deg_by_class: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_MAX_ERROR_DEG)
    )
    walk_error_ratio: float = 0.50      # 靜步 = 最大誤差 × 0.50
    crouch_error_ratio: float = 0.35    # 蹲走 = 最大誤差 × 0.35
    airborne_error_ratio: float = 1.25  # 空中 = 最大誤差 × 1.25
    land_error_deg: float = 7.0         # 落地額外懲罰（度）
    land_error_time: float = 0.225      # 落地懲罰持續時間（秒）


class MovementErrorEngine:
    """將移動狀態轉換為「額外擴散角度」的純函式引擎。"""

    def __init__(self, cfg: AccuracyConfig | None = None):
        self.cfg = cfg if cfg is not None else AccuracyConfig()

    def error_deg(
        self,
        speed_ratio: float,
        walking: bool,
        crouching: bool,
        airborne: bool,
        time_since_land: float,
        weapon_class: str,
    ) -> float:
        """
        計算移動造成的額外擴散角度（度）。

        :param speed_ratio:   目前水平速度 / 跑速（0..1）
        :param walking:       是否按 Shift 靜步
        :param crouching:     是否下蹲
        :param airborne:      是否在空中
        :param time_since_land: 距離上次落地的秒數
        :param weapon_class:  武器類別（sidearm/smg/rifle/sniper/shotgun/heavy）
        """
        max_err = self.cfg.max_error_deg_by_class.get(weapon_class, 2.0)
        ratio = clamp(speed_ratio, 0.0, 1.0)

        if airborne:
            base = max_err * self.cfg.airborne_error_ratio
        elif crouching:
            base = max_err * self.cfg.crouch_error_ratio * ratio
        elif walking:
            base = max_err * self.cfg.walk_error_ratio * ratio
        else:
            base = max_err * ratio   # 跑步：100% 誤差

        # 落地懲罰：0.225s 內線性衰減至 0
        land = 0.0
        if time_since_land < self.cfg.land_error_time:
            land = self.cfg.land_error_deg * (
                1.0 - time_since_land / self.cfg.land_error_time
            )
        return base + land

    def error_for(self, controller, weapon_class: str) -> float:
        """從 MovementController 直接取值的便捷介面。"""
        return self.error_deg(
            speed_ratio=controller.speed_ratio(),
            walking=controller.walking,
            crouching=controller.crouching,
            airborne=not controller.on_ground,
            time_since_land=controller.time_since_land,
            weapon_class=weapon_class,
        )
