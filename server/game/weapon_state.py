"""
server/game/weapon_state.py — 單把武器的狀態
=============================================
從 entities.py 抽離（避免 inventory ↔ entities 循環匯入）：
彈匣/備彈/換彈進度/後座力/開火冷卻，全部伺服器權威。
"""

from __future__ import annotations

from server.game.recoil import RecoilController, pattern_for


class WeaponState:
    def __init__(self, stats, rng):
        self.stats = stats
        self.rng = rng
        self.mag = stats.mag_size
        self.reserve = stats.reserve
        self.reloading = False
        self.reload_progress = 0.0
        self.next_fire_time = 0.0
        self.recoil = RecoilController(pattern_for(stats), rng)
        self.aim_pitch_offset = 0.0
        self.aim_yaw_offset = 0.0
        # Odin 旋轉加速：連續開火時射速逐漸提升（特戰式）
        self._sustained_fire_time = 0.0  # 持續開火累計時間
        self._last_fire_time = -1e9

    def can_fire(self, now: float) -> bool:
        return not self.reloading and now >= self.next_fire_time and self.mag > 0

    def attempt_fire(self, now: float) -> bool:
        """開火：消耗彈藥、推進後座力、設定冷卻。回傳是否成功。"""
        if not self.can_fire(now):
            return False
        self.mag -= 1
        self.recoil.fire(now)
        # 準線偏移 = 後座控制器的「累積值」（會隨停火恢復）。
        # 舊寫法是 `+= p` 只增不減：壓完整個彈匣後準線永久停在上緣，之後每一發
        # 都跟著歪，而且不會隨時間回來——那會把「壓槍→放開recover」的手感整個抹平。
        self.aim_pitch_offset = self.recoil.pitch
        self.aim_yaw_offset = self.recoil.yaw
        # Odin 旋轉加速：持續開火時射速提升（12→15.6 rps）
        fire_rate = self.stats.fire_rate_rps
        if self.stats.key == "odin":
            gap = now - self._last_fire_time
            if gap < 0.3:  # 連續開火中
                self._sustained_fire_time += gap
                # 0~1.5s 線性加速到 1.3 倍
                boost = 1.0 + min(self._sustained_fire_time / 1.5, 1.0) * 0.3
                fire_rate = self.stats.fire_rate_rps * boost
            else:
                self._sustained_fire_time = 0.0
            self._last_fire_time = now
        self.next_fire_time = now + 1.0 / fire_rate
        if self.mag <= 0:
            self.start_reload(now)
        return True

    def start_reload(self, now: float) -> bool:
        if self.reloading or self.mag >= self.stats.mag_size or self.reserve <= 0:
            return False
        self.reloading = True
        self.reload_progress = 0.0
        return True

    def update(self, now: float, dt: float) -> None:
        self.recoil.update(now, dt)
        # 恢復要即時反映到準線（entities 每發都讀這兩個欄位）
        self.aim_pitch_offset = self.recoil.pitch
        self.aim_yaw_offset = self.recoil.yaw
        if self.reloading:
            self.reload_progress += dt
            if self.reload_progress >= self.stats.reload_time:
                need = self.stats.mag_size - self.mag
                take = min(need, self.reserve)
                self.mag += take
                self.reserve -= take
                self.reloading = False
                # 換彈完成 → 图案回到第 1 發（「首發最準」是點射流派的根基）
                self.recoil.reset_pattern()

    def reset_ammo(self) -> None:
        self.mag = self.stats.mag_size
        self.reserve = self.stats.reserve
        self.reloading = False
        self.reload_progress = 0.0

    def snapshot(self) -> dict:
        return {
            "key": self.stats.key, "mag": self.mag, "reserve": self.reserve,
            "reloading": self.reloading,
        }
