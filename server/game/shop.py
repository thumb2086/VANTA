"""
server/game/shop.py — Night Market + Daily Shop (Valorant-style)
===============================================================
* SkinTier: SELECT/DELUXE/PREMIUM/ULTRA/EXCLUSIVE (5 tiers)
* SkinDef: weapon_key, name, tier, price_vp, variants (color list)
* ALL_SKINS: catalog of 40+ skins (5 weapons × 8 skins each, all tiers)
* NightMarket: 6 random discounted skins per player per day (seeded)
* DailyShop: 4 featured skins, resets every 24h
* PurchaseSkin: deducts VP, records ownership
"""
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from enum import Enum


class SkinTier(Enum):
    SELECT = 0
    DELUXE = 1
    PREMIUM = 2
    ULTRA = 3
    EXCLUSIVE = 4


TIER_PRICES = {0: 10, 1: 20, 2: 35, 3: 50, 4: 80}  # VP


@dataclass
class SkinDef:
    id: str
    weapon_key: str
    name: str
    tier: SkinTier
    price_vp: int = 0
    variants: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.price_vp == 0:
            self.price_vp = TIER_PRICES[self.tier.value]


# ---------------------------------------------------------------------------
# 40 skins: 5 weapons × 8 names × tier mix
# ---------------------------------------------------------------------------
_SKIN_NAMES = {
    "vandal": [
        "貴族 Vandal", "暗影之刃 Vandal", "星塵 Vandal", "深淵 Vandal",
        "極光 Vandal", "龍炎 Vandal", "暴風 Vandal", "冰霜 Vandal",
    ],
    "phantom": [
        "掠奪者 Phantom", "源計畫 Phantom", "極光 Phantom", "龍炎 Phantom",
        "暗影 Phantom", "星芒 Phantom", "冰霜 Phantom", "烈焰 Phantom",
    ],
    "classic": [
        "毒素之牙 Classic", "暴走 Classic", "日蝕 Classic", "冰霜 Classic",
        "暗影 Classic", "星芒 Classic", "極光 Classic", "龍炎 Classic",
    ],
    "knife": [
        "黃金 匕首", "鋒芒 匕首", "暗影 匕首", "冰霜 匕首",
        "極光 匕首", "星芒 匕首", "龍炎 匕首", "烈焰 匕首",
    ],
    "ghost": [
        "光之哨兵 Ghost", "冰霜幻影 Ghost", "日蝕 Ghost", "暗影 Ghost",
        "星芒 Ghost", "極光 Ghost", "龍炎 Ghost", "暴風 Ghost",
    ],
}

_TIER_SEQUENCE = [
    SkinTier.SELECT, SkinTier.DELUXE, SkinTier.PREMIUM, SkinTier.ULTRA,
    SkinTier.EXCLUSIVE, SkinTier.SELECT, SkinTier.DELUXE, SkinTier.PREMIUM,
]

ALL_SKINS: list[SkinDef] = []
for _wk, _names in _SKIN_NAMES.items():
    for _i, _nm in enumerate(_names):
        ALL_SKINS.append(SkinDef(
            id=f"{_wk}_{_i}",
            weapon_key=_wk,
            name=_nm,
            tier=_TIER_SEQUENCE[_i],
        ))


# ---------------------------------------------------------------------------
# Night Market — 6 random discounted skins per player per day (seeded)
# ---------------------------------------------------------------------------
def generate_night_market(player_id: int, date_str: str) -> list[dict]:
    h = int(hashlib.sha256(f"{player_id}:{date_str}".encode()).hexdigest(), 16)
    rng = random.Random(h)
    pool = list(ALL_SKINS)
    rng.shuffle(pool)
    chosen = pool[:6]
    discounts = [rng.randint(30, 50) for _ in range(6)]
    return [
        {
            "skin_id": s.id,
            "name": s.name,
            "weapon": s.weapon_key,
            "tier": s.tier.value,
            "original_vp": s.price_vp,
            "discount_pct": d,
            "sale_vp": s.price_vp * (100 - d) // 100,
        }
        for s, d in zip(chosen, discounts)
    ]


# ---------------------------------------------------------------------------
# Daily Shop — 4 featured skins, resets every 24h
# ---------------------------------------------------------------------------
def generate_daily_shop(date_str: str) -> list[dict]:
    h = int(hashlib.sha256(date_str.encode()).hexdigest(), 16)
    rng = random.Random(h)
    pool = list(ALL_SKINS)
    rng.shuffle(pool)
    return [
        {
            "skin_id": s.id,
            "name": s.name,
            "weapon": s.weapon_key,
            "tier": s.tier.value,
            "price_vp": s.price_vp,
        }
        for s in pool[:4]
    ]


# ---------------------------------------------------------------------------
# Player Shop State
# ---------------------------------------------------------------------------
@dataclass
class PlayerShopState:
    vp: int = 5000
    owned_skins: list[str] = field(default_factory=list)
    equipped: dict[str, str] = field(default_factory=dict)  # weapon_key -> skin_id
    night_market: list[dict] = field(default_factory=list)
    daily_shop: list[dict] = field(default_factory=list)

    def purchase(self, skin_id: str, price_vp: int) -> bool:
        if self.vp < price_vp or skin_id in self.owned_skins:
            return False
        self.vp -= price_vp
        self.owned_skins.append(skin_id)
        return True

    def equip(self, weapon_key: str, skin_id: str) -> bool:
        if skin_id not in self.owned_skins:
            return False
        self.equipped[weapon_key] = skin_id
        return True

    def refresh_shops(self, player_id: int, date_str: str) -> None:
        self.night_market = generate_night_market(player_id, date_str)
        self.daily_shop = generate_daily_shop(date_str)
