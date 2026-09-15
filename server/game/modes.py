"""
server/game/modes.py — 快速對戰模式（對標 Valorant 好玩原則 P1/P2/P7/P9）
=====================================================================
* Spike Rush（Bo7 先到 4）：全場每回合同一把隨機槍＋護甲遞增，
  全員可安包（VANTA spike 本來就無攜帶者限制），技能每回合免費，
  地圖 1–5 顆 Powerup Orb（武器升級/治療/刺激/偏執/金槍）。
* Swiftplay（Bo9 先到 5）：標準規則濃縮，固定經濟配給表。
* competitive / deathmatch 維持原樣（見 match.py）。

設計來源：docs/valorant_patch_research.md §二 P1/P2/P7。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from server.core.math_core import Vec3
from server.game.status import NEARSIGHT, DEAFENED, SPEED_BOOST
from server.game.weapons import WEAPONS, weapon

# ---------------------------------------------------------------------- #
# 模式 ID
# ---------------------------------------------------------------------- #
COMPETITIVE = "competitive"
DEATHMATCH = "deathmatch"
SPIKERUSH = "spikerush"
SWIFTPLAY = "swiftplay"
QUICK_MODES = (SPIKERUSH, SWIFTPLAY)

# ---------------------------------------------------------------------- #
# Spike Rush：回合配裝表（官方規則簡化）
# ---------------------------------------------------------------------- #
SR_ROUNDS_TO_WIN = 4
SR_HALF_ROUNDS = 3          # 3 回合後換邊
SR_BUY_TIME = 20.0
SR_ACTION_TIME = 80.0

SR_SIDEARMS = ("classic", "shorty", "frenzy", "ghost", "bandit", "sheriff")
SR_TIER2 = ("stinger", "spectre", "bucky", "judge", "bulldog", "marshal", "ares")
SR_TIER3 = ("guardian", "phantom", "vandal", "outlaw", "operator", "odin")
SR_SHIELD = {1: 0, 2: 25}   # 第 3 回合起 50（official: Endgame heavy）


def sr_round_weapon(rng: random.Random, round_in_half: int) -> str:
    """第幾回合（半場內 1-based）→ 該回合全場武器。"""
    if round_in_half <= 1:
        pool = SR_SIDEARMS
    elif round_in_half == 2:
        pool = SR_TIER2
    else:
        pool = SR_TIER3
    return rng.choice(pool)


def sr_round_shield(round_in_half: int) -> int:
    if round_in_half <= 1:
        return 0
    if round_in_half == 2:
        return 25
    return 50


def sr_upgrade_weapon(rng: random.Random, current_key: str) -> str:
    """Weapon Upgrade Orb：給下一階隨機槍（tier3 則給 Operator/Odin）。"""
    if current_key in SR_SIDEARMS:
        pool = SR_TIER2
    elif current_key in SR_TIER2:
        pool = SR_TIER3
    else:
        pool = ("operator", "odin")
    choices = [w for w in pool if w != current_key] or list(pool)
    return rng.choice(choices)


# ---------------------------------------------------------------------- #
# Swiftplay：濃縮經濟表（官方：800 → 2400(+600) → 4250 → 4250 → 5000）
# ---------------------------------------------------------------------- #
SP_ROUNDS_TO_WIN = 5
SP_HALF_ROUNDS = 4          # 4 回合後換邊
SP_BUY_TIME = 20.0
SP_ACTION_TIME = 100.0
SP_GRANTS = {1: 800, 2: 2400, 3: 4250, 4: 4250}
SP_WIN_BONUS = 600
SP_OVERTIME_GRANT = 5000


def sp_round_grant(round_in_half: int, won_prev: bool) -> int:
    base = SP_GRANTS.get(round_in_half, SP_OVERTIME_GRANT)
    if round_in_half == 2 and won_prev:
        base += SP_WIN_BONUS
    return base


# ---------------------------------------------------------------------- #
# Spike Rush Powerup Orbs
# ---------------------------------------------------------------------- #
ORB_WEAPON_UPGRADE = "weapon_upgrade"
ORB_HEAL = "heal_team"
ORB_STIM = "stim_team"
ORB_PARANOIA = "paranoia"
ORB_GOLDEN = "golden_gun"
ORB_TYPES = (ORB_WEAPON_UPGRADE, ORB_HEAL, ORB_STIM, ORB_PARANOIA, ORB_GOLDEN)

ORB_CAPTURE_RADIUS = 1.5
ORB_GOLDEN_MULT = 4.0       # 金槍：傷害 ×4（兩槍身體必倒，爆頭一槍）
ORB_GOLDEN_DURATION = 45.0


@dataclass
class OrbPickup:
    kind: str
    pos: Vec3
    captured: bool = False
    captured_by: int = -1


@dataclass
class OrbField:
    """一回合的 orb 集合：產生＋捕獲判定。由 Match 在回合開始時重建。"""
    orbs: list[OrbPickup] = field(default_factory=list)

    def spawn_for_round(self, rng: random.Random, map_data, round_number: int) -> None:
        spots: list[Vec3] = []
        for s in getattr(map_data, "sites", []):
            c = s.center if hasattr(s, "center") else s.get("center")
            spots.append(Vec3(c.x, 0.0, c.z) if not isinstance(c, Vec3) else Vec3(c.x, 0.0, c.z))
        spots.append(Vec3(0.0, 0.0, 0.0))  # 中路
        n = min(len(spots), 1 + (rng.randrange(5) if hasattr(rng, "randrange") else int(rng.random() * 5)))
        kinds = list(ORB_TYPES)
        # 洗牌（只用 random()，相容 random.Random 與確定性 rng）
        for i in range(len(kinds) - 1, 0, -1):
            j = int(rng.random() * (i + 1))
            kinds[i], kinds[j] = kinds[j], kinds[i]
        self.orbs = [OrbPickup(kind=kinds[i % len(kinds)], pos=spots[i]) for i in range(n)]

    def update(self, world) -> list[str]:
        """捕獲判定。回傳事件字串（寫入 world.event_log 由呼叫端決定）。"""
        events: list[str] = []
        for orb in self.orbs:
            if orb.captured:
                continue
            for p in world.players:
                if not p.alive:
                    continue
                d = p.pos - orb.pos
                if d.x * d.x + d.z * d.z <= ORB_CAPTURE_RADIUS ** 2:
                    orb.captured = True
                    orb.captured_by = p.slot
                    events.append(_apply_orb(world, orb, p.slot))
                    break
        return events


def _apply_orb(world, orb: OrbPickup, slot: int) -> str:
    p = world.players[slot]
    if orb.kind == ORB_WEAPON_UPGRADE:
        cur = p.inventory.active_state().stats.key if hasattr(p.inventory.active_state(), "stats") else "classic"
        new_key = sr_upgrade_weapon(world.rng, cur)
        p.grant_weapon(new_key)
        return f"orb: slot{slot} weapon_upgrade -> {new_key}"
    if orb.kind == ORB_HEAL:
        for q in world.players:
            if q.team == p.team and q.alive:
                q.health = min(100.0, q.health + 50.0)
        return f"orb: slot{slot} heal_team"
    if orb.kind == ORB_STIM:
        for q in world.players:
            if q.team == p.team and q.alive:
                q.status.apply(SPEED_BOOST, 20.0, 1.0)
        return f"orb: slot{slot} stim_team"
    if orb.kind == ORB_PARANOIA:
        for q in world.players:
            if q.team != p.team and q.alive:
                q.status.apply(NEARSIGHT, 10.0, 1.0)
                q.status.apply(DEAFENED, 10.0, 1.0)
        return f"orb: slot{slot} paranoia"
    if orb.kind == ORB_GOLDEN:
        p.status.apply("damage_boost", ORB_GOLDEN_DURATION, ORB_GOLDEN_MULT)
        return f"orb: slot{slot} golden_gun"
    return f"orb: slot{slot} unknown({orb.kind})"


# ---------------------------------------------------------------------- #
# 模式參數總表（Match 取用）
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModeRules:
    mode: str
    rounds_to_win: int
    half_rounds: int
    buy_time_first: float
    buy_time_normal: float
    action_time: float
    has_spike: bool = True
    free_loadout: bool = False   # Spike Rush：每回合免費配裝
    fixed_economy: bool = False  # Swiftplay：固定配給


MODE_RULES: dict[str, ModeRules] = {
    COMPETITIVE: ModeRules(COMPETITIVE, 13, 12, 30.0, 30.0, 100.0),
    DEATHMATCH: ModeRules(DEATHMATCH, 0, 0, 0.0, 0.0, 0.0, has_spike=False),
    SPIKERUSH: ModeRules(SPIKERUSH, SR_ROUNDS_TO_WIN, SR_HALF_ROUNDS, SR_BUY_TIME, SR_BUY_TIME,
                         SR_ACTION_TIME, free_loadout=True),
    SWIFTPLAY: ModeRules(SWIFTPLAY, SP_ROUNDS_TO_WIN, SP_HALF_ROUNDS, SP_BUY_TIME, SP_BUY_TIME,
                         SP_ACTION_TIME, fixed_economy=True),
}


def mode_rules(mode: str) -> ModeRules:
    if mode not in MODE_RULES:
        raise KeyError(f"unknown mode: {mode}")
    return MODE_RULES[mode]


def all_weapons() -> list[str]:
    return sorted(WEAPONS.keys())
