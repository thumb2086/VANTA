"""
server/game/inventory.py — 武器槽位與切換
=========================================
《特戰英豪》式武器配置：主武器(0) / 副武器(1) / 近戰刀(2)。
  * 切換立即生效（快照可即時反映），但切換期間不可開火（switch_time 門控）
  * 刀切換更快（0.45s），長槍較慢（0.65s）
  * 每個槽位保有獨立的 WeaponState（彈匣/後座力/換彈各自獨立）
"""

from __future__ import annotations

from server.game.weapon_state import WeaponState


class WeaponInventory:
    def __init__(self, rng):
        from server.game.weapons import weapon

        self.slots: dict[int, WeaponState] = {
            0: None,                                   # 主武器（可購買）
            1: WeaponState(weapon("classic"), rng),    # 副武器（預設手槍）
            2: WeaponState(weapon("knife"), rng),      # 近戰
        }
        self.active = 1
        self.switch_until = -1.0      # 世界時間：切換完成後才可開火

    # ------------------------------------------------------------------ #
    def active_state(self) -> WeaponState:
        return self.slots[self.active]

    def switch_duration(self, slot: int) -> float:
        return 0.45 if slot == 2 else 0.65

    def start_switch(self, slot: int, now: float) -> bool:
        """切換到指定槽位（立即生效，切換期間不可開火）。"""
        if slot not in self.slots or self.slots[slot] is None:
            return False
        if slot == self.active:
            return False
        self.active = slot
        self.switch_until = now + self.switch_duration(slot)
        return True

    def switching(self, now: float) -> bool:
        return now < self.switch_until

    def install_primary(self, ws: WeaponState) -> None:
        self.slots[0] = ws

    def reset_all(self) -> None:
        for s in self.slots.values():
            if s is not None:
                s.reset_ammo()
