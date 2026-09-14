"""
server/game/economy.py — M8 經濟運算核心
========================================
公式（近似《特戰英豪》，來源見 docs/00_research_notes.md）：
  * 擊殺獎勵        +200（立即發放，上限 9000）
  * 回合勝利        +3000（全隊）
  * 回合敗北（連敗） 1900 → 2400 → 2900（第 3 連敗起封頂 2900）
  * 安放 Spike      +300（攻方全員）
  * 半場開始        800
  * 資金上限        9000（超出歸零）
連敗數以「包含本回合」的連續敗場計算。
"""

from __future__ import annotations

from dataclasses import dataclass

CREDITS_MAX = 9000
CREDITS_START = 800
KILL_REWARD = 200
ROUND_WIN_REWARD = 3000
SPIKE_PLANT_REWARD = 300
LIGHT_SHIELD_HP = 25
HEAVY_SHIELD_HP = 50
LIGHT_SHIELD_PRICE = 400
HEAVY_SHIELD_PRICE = 1000


def loss_bonus(loss_streak: int) -> int:
    """連敗補償：1 場 1900，2 場 2400，3 場起 2900（封頂）。"""
    if loss_streak <= 1:
        return 1900
    if loss_streak == 2:
        return 2400
    return 2900


@dataclass(slots=True)
class EconomyComponent:
    credits: int = CREDITS_START

    def grant(self, amount: int) -> None:
        self.credits = min(CREDITS_MAX, self.credits + amount)

    def can_afford(self, price: int) -> bool:
        return self.credits >= price

    def buy(self, price: int) -> bool:
        if not self.can_afford(price):
            return False
        self.credits -= price
        return True
