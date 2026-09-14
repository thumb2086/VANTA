"""
server/game/weapons.py — M4 武器資料庫
======================================
所有數值為「開放專案的近似值」（Riot 未公開精確參數），
集中在資料表以利日後校正。含傷害衰減公式與傷害計算。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DamageFalloff:
    range_min: float          # 此距離內為全傷
    range_max: float          # 此距離以上為最低傷
    dmg_max: float            # 全傷
    dmg_min: float            # 最低傷


@dataclass(frozen=True, slots=True)
class WeaponStats:
    key: str
    name: str
    wclass: str               # sidearm/smg/rifle/sniper/shotgun/heavy
    price: int
    fire_rate_rps: float      # 每秒射速
    mag_size: int
    reserve: int
    reload_time: float
    damage: float             # 基礎傷害（身體 1x）
    falloff: DamageFalloff | None
    penetration_level: int    # 0..3（見 mapdata）
    first_shot_accuracy: float  # 度
    spread_per_bullet: float  # 每發擴散成長（度）
    move_speed_mult: float
    ads_spread_mult: float
    automatic: bool
    burst: int = 1
    pellets: int = 1          # 霰彈槍彈丸數
    scoped: bool = False


def damage_at(stats: WeaponStats, dist: float) -> float:
    """依距離計算傷害（無衰減則恆定）。"""
    if stats.falloff is None:
        return stats.damage
    f = stats.falloff
    if dist <= f.range_min:
        return f.dmg_max
    if dist >= f.range_max:
        return f.dmg_min
    t = (dist - f.range_min) / (f.range_max - f.range_min)
    return f.dmg_max + (f.dmg_min - f.dmg_max) * t


def _no_falloff():
    return None


def _falloff(rmin, rmax, dmax, dmin):
    return DamageFalloff(rmin, rmax, dmax, dmin)


WEAPONS: dict[str, WeaponStats] = {}


def _reg(w: WeaponStats) -> None:
    WEAPONS[w.key] = w


# --- 手槍 (sidearm) ---
_reg(WeaponStats("classic", "Classic", "sidearm", 0, 6.75, 12, 60, 1.5, 26, None, 0, 0.2, 0.02, 1.0, 0.85, True, burst=3))
_reg(WeaponStats("ghost", "Ghost", "sidearm", 500, 6.75, 15, 45, 1.5, 30, None, 0, 0.2, 0.02, 1.0, 0.85, True))
_reg(WeaponStats("bandit", "Bandit", "sidearm", 600, 4.0, 8, 24, 1.5, 40, _falloff(20, 50, 40, 30), 1, 0.25, 0.015, 1.0, 0.85, False))
_reg(WeaponStats("sheriff", "Sheriff", "sidearm", 800, 4.0, 6, 18, 2.0, 55, None, 0, 0.3, 0.01, 1.0, 0.85, False))
_reg(WeaponStats("frenzy", "Frenzy", "sidearm", 450, 10.0, 13, 39, 1.5, 26, None, 0, 0.5, 0.03, 1.0, 0.85, True))
_reg(WeaponStats("shorty", "Shorty", "sidearm", 300, 3.3, 2, 10, 1.0, 12, None, 0, 0.9, 0.1, 1.0, 0.85, False, pellets=12))
# --- 衝鋒槍 (smg) ---
_reg(WeaponStats("stinger", "Stinger", "smg", 1100, 18.0, 20, 60, 1.8, 27, _falloff(20, 50, 27, 22), 1, 0.6, 0.05, 0.98, 0.6, False, burst=4))
_reg(WeaponStats("spectre", "Spectre", "smg", 1600, 13.33, 30, 90, 2.1, 26, _falloff(15, 30, 26, 20), 1, 0.5, 0.04, 0.98, 0.6, True))
# --- 步槍 (rifle) ---
_reg(WeaponStats("bulldog", "Bulldog", "rifle", 2050, 9.15, 24, 72, 2.5, 35, _falloff(30, 50, 35, 31), 2, 0.25, 0.03, 0.95, 0.55, False, burst=3))
_reg(WeaponStats("guardian", "Guardian", "rifle", 2250, 6.5, 12, 36, 2.5, 65, None, 2, 0.2, 0.02, 0.92, 0.55, False))
_reg(WeaponStats("phantom", "Phantom", "rifle", 2900, 11.0, 30, 90, 2.5, 39, _falloff(15, 50, 39, 31), 2, 0.2, 0.04, 0.95, 0.55, True))
_reg(WeaponStats("vandal", "Vandal", "rifle", 2900, 9.75, 25, 75, 2.5, 40, None, 2, 0.25, 0.05, 0.95, 0.55, True))
# --- 狙擊 (sniper) ---
_reg(WeaponStats("marshal", "Marshal", "sniper", 950, 1.5, 5, 15, 2.5, 101, None, 2, 0.15, 0.01, 0.90, 0.35, False, scoped=True))
_reg(WeaponStats("outlaw", "Outlaw", "sniper", 2400, 1.2, 5, 15, 3.0, 140, None, 2, 0.1, 0.01, 0.80, 0.30, False, scoped=True))
_reg(WeaponStats("operator", "Operator", "sniper", 4700, 0.75, 5, 15, 3.7, 150, None, 2, 0.05, 0.01, 0.70, 0.25, False, scoped=True))
# --- 霰彈 (shotgun) ---
_reg(WeaponStats("bucky", "Bucky", "shotgun", 850, 1.1, 5, 15, 2.5, 20, _falloff(8, 20, 20, 8), 1, 0.8, 0.1, 0.96, 0.6, False, pellets=15))
_reg(WeaponStats("judge", "Judge", "shotgun", 1850, 3.5, 7, 21, 2.2, 17, _falloff(10, 20, 17, 7), 1, 0.9, 0.1, 0.95, 0.6, True, pellets=12))
# --- 重武器 (heavy) ---
_reg(WeaponStats("ares", "Ares", "heavy", 1600, 13.0, 50, 150, 4.2, 30, None, 2, 0.4, 0.05, 0.85, 0.55, True))
_reg(WeaponStats("odin", "Odin", "heavy", 3200, 12.0, 100, 300, 5.0, 38, None, 2, 0.5, 0.06, 0.80, 0.55, True))
# --- 近戰 ---
_reg(WeaponStats("knife", "Knife", "melee", 0, 1.5, 1, 0, 0.0, 50, None, 0, 0.0, 0.0, 1.0, 1.0, False))


def weapon(key: str) -> WeaponStats:
    if key not in WEAPONS:
        raise KeyError(f"unknown weapon: {key}")
    return WEAPONS[key]
