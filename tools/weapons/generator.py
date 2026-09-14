"""
tools/weapons/generator.py — seed 驅動武器產生器
================================================
以種子隨機組合「接收器 + 模組」，產生獨特改裝槍，並驗證數值平衡。

使用：
    mw = generate_weapon(seed=42, frame_key="vandal")
    stats = mw.stats()                      # 可直接進遊戲 (WeaponStats)
    summary = mw.summary()                  # 匯出 JSON
"""

from __future__ import annotations

import random

from server.game.weapons import WEAPONS, WeaponStats
from tools.weapons.modular import MOD_POOL, ModdableWeapon, frame_from_weapon

# 可選作為接收器的武器（步槍/衝鋒槍/重武 才有模組化價值）
FRAME_KEYS = ("vandal", "phantom", "bulldog", "guardian", "spectre", "stinger", "ares", "odin")

# 平衡上下限（產生後驗證；需涵蓋所有接收器基礎值 + 模組疊加範圍）
BALANCE_LIMITS: dict[str, tuple[float, float]] = {
    "damage": (20.0, 75.0),
    "fire_rate_rps": (3.0, 19.0),
    "mag_size": (5, 140),
    "reload_time": (0.5, 7.0),
    "spread_per_bullet": (0.0, 0.2),
    "price": (0, 9000),
}

# 命名後綴池
NAME_SUFFIXES = ("Mk.II", "戰術型", "特種型", "競賽型", "夜戰型", "追擊者", "破壞者")


def generate_weapon(seed: int, frame_key: str = "vandal", max_mods: int = 4) -> ModdableWeapon:
    """依 seed 產生一把模組化武器（0..max_mods 個模組，槽位不重複）。"""
    rng = random.Random(seed)
    frame = frame_from_weapon(frame_key)
    mw = ModdableWeapon(frame)
    slots = list(frame.slots)
    rng.shuffle(slots)
    n = rng.randint(1, max_mods)
    for slot in slots[:n]:
        pool = MOD_POOL.get(slot, [])
        if not pool:
            continue
        mw.install(slot, rng.choice(pool))
    return mw


def validate_balance(stats: WeaponStats) -> list[str]:
    """檢查數值是否超出平衡範圍。回傳問題清單（空 = 通過）。"""
    issues: list[str] = []
    checks = {
        "damage": stats.damage,
        "fire_rate_rps": stats.fire_rate_rps,
        "mag_size": float(stats.mag_size),
        "reload_time": stats.reload_time,
        "spread_per_bullet": stats.spread_per_bullet,
        "price": float(stats.price),
    }
    for stat, value in checks.items():
        lo, hi = BALANCE_LIMITS[stat]
        if not (lo <= value <= hi):
            issues.append(f"{stat}={value:.2f} 超出 [{lo}, {hi}]")
    return issues


def generate_batch(seed: int, frame_keys: list[str] | None = None, count: int = 8) -> list[ModdableWeapon]:
    """產生一批武器（每個 frame 一把，seed 遞增）。"""
    keys = frame_keys or FRAME_KEYS
    out = []
    for i in range(count):
        k = keys[i % len(keys)]
        out.append(generate_weapon(seed + i, frame_key=k))
    return out


def register_to_game(mw: ModdableWeapon) -> str:
    """將模組化武器註冊進 server.game.weapons.WEAPONS（key 可被遊戲使用）。"""
    stats = mw.stats()
    WEAPONS[stats.key] = stats
    return stats.key
