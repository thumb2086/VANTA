"""
server/game/status.py — M13 狀態干擾 (Debuffs)
==============================================
八種狀態：
  * BLINDED 閃瞎  ：無法開火 + 視野封鎖（渲染層畫布白屏/漸層遮罩）
  * CONCUSSED 暈眩：移動速度下降 + FOV 收縮（控制器干擾）
  * VULNERABLE 易傷：受到的傷害 ×(1+potency)
  * SPEED_BOOST 加速：移動速度提升 ×(1+0.25×potency)
  * NEARSIGHT 近視：視野半徑縮小（Fade Prowler / Breach Flash）
  * SUPPRESSED 封鎖：無法使用技能（KAY/O suppression）
  * DECAY 衰減：每秒持續扣血（Viper 毒霧 / Fade 終極）
  * SLOW 減速：移動速度 ×0.5（Sage Slow Orb）
  * DEAFENED 聽覺封鎖：環境音降低（Breach / Omen）
  * REVEALED 偵測：位置被敵方可見（Cypher / Sova）
疊加規則：同型態以「剩餘時間最長」者勝出，potency 取最高。
"""

from __future__ import annotations

from dataclasses import dataclass, field

BLIND = "blind"
CONCUSS = "concuss"
VULNERABLE = "vulnerable"
SPEED_BOOST = "speed_boost"
NEARSIGHT = "nearsight"       # 近視：視野縮小（Sova Seeker / Fade Prowler）
SUPPRESSED = "suppressed"      # 技能封鎖：無法使用技能（KAY/O）
DECAY = "decay"               # 持續扣血（Viper 毒霧 / Fade 終極）
SLOW = "slow"                  # 減速：移動速度下降（Sage Slow Orb）
DEAFENED = "deafened"          # 聽覺封鎖：環境音降低（Breach / Omen）
REVEALED = "revealed"          # 被偵測：位置被敵方可見（Cypher / Sova）
DAMAGE_BOOST = "damage_boost"  # 傷害提升：造成的傷害 ×potency（Spike Rush 金槍）


@dataclass(slots=True)
class ActiveStatus:
    kind: str
    time_left: float
    potency: float


class StatusEffectSystem:
    def __init__(self):
        self.statuses: list[ActiveStatus] = []

    def apply(self, kind: str, duration: float, potency: float = 1.0) -> None:
        # 同型態以長者勝出、potency 取最高
        for s in self.statuses:
            if s.kind == kind:
                s.time_left = max(s.time_left, duration)
                s.potency = max(s.potency, potency)
                return
        self.statuses.append(ActiveStatus(kind, duration, potency))

    def update(self, dt: float) -> None:
        for s in self.statuses:
            s.time_left -= dt
        self.statuses = [s for s in self.statuses if s.time_left > 0.0]

    def tick_decay(self, dt: float, player=None) -> float:
        """處理 Decay 持續傷害。回傳本 tick 的傷害量。"""
        if not self.has(DECAY):
            return 0.0
        dmg = self.has_decay * dt
        if player is not None and dmg > 0:
            player.health -= dmg
            if player.health <= 0 and player.alive:
                player.health = 0.0
                player.alive = False
                player.deaths += 1
                if player.world is not None:
                    player.world._on_player_killed(player.slot, -1, "decay")
        return dmg

    def has(self, kind: str) -> bool:
        return any(s.kind == kind for s in self.statuses)

    def potency(self, kind: str) -> float:
        for s in self.statuses:
            if s.kind == kind:
                return s.potency
        return 0.0

    # --- 控制器干擾查詢（供移動/射擊/渲染層使用）---
    @property
    def move_speed_mult(self) -> float:
        """暈眩 → 0.65；加速 → ×(1 + 0.25×potency)；減速 → ×0.5；兩者相乘疊加。"""
        base = 1.0
        if self.has(CONCUSS):
            base *= 0.65
        if self.has(SLOW):
            base *= 0.5
        boost = 1.0 + 0.25 * self.potency(SPEED_BOOST)
        return base * boost

    @property
    def damage_taken_mult(self) -> float:
        """易傷 → ×(1+potency)。"""
        return 1.0 + self.potency(VULNERABLE)

    @property
    def damage_dealt_mult(self) -> float:
        """傷害提升（金槍）→ ×potency，無則 1.0。"""
        return self.potency(DAMAGE_BOOST) if self.has(DAMAGE_BOOST) else 1.0

    @property
    def can_shoot(self) -> bool:
        return not self.has(BLIND)

    @property
    def can_use_ability(self) -> bool:
        """被技能封鎖時無法使用技能（KAY/O suppression）。"""
        return not self.has(SUPPRESSED)

    @property
    def sight_blocked(self) -> bool:
        return self.has(BLIND)

    @property
    def has_decay(self) -> float:
        """回傳每秒持續傷害量（Decay）。"""
        return self.potency(DECAY) if self.has(DECAY) else 0.0

    def render_state(self) -> list[dict]:
        """畫布渲染狀態（供客戶端渲染層：白屏遮罩/暈眩花紋/易傷色邊）。"""
        return [
            {"kind": s.kind, "time_left": s.time_left, "potency": s.potency}
            for s in self.statuses
        ]
