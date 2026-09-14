/// weapon_state.rs — 單把武器的狀態（對齊 Python server/game/weapon_state.py）
///
/// 彈匣/備彈/換彈進度/後座力/開火冷卻，全部伺服器權威。
/// Odin 旋轉加速：連續開火時射速逐漸提升（特戰式）

use super::recoil::RecoilController;
use super::weapons::WeaponStats;

pub struct WeaponState {
    pub stats: &'static WeaponStats,
    pub mag: u32,
    pub reserve: u32,
    pub reloading: bool,
    pub reload_progress: f64,
    pub next_fire_time: f64,
    pub recoil: RecoilController,
    pub aim_pitch_offset: f64,
    pub aim_yaw_offset: f64,
    // Odin 旋轉加速
    sustained_fire_time: f64,
    last_fire_time: f64,
}

impl WeaponState {
    pub fn new(stats: &'static WeaponStats, recoil: RecoilController) -> Self {
        let mag = stats.mag_size;
        let reserve = stats.reserve;
        Self {
            stats,
            mag,
            reserve,
            reloading: false,
            reload_progress: 0.0,
            next_fire_time: 0.0,
            recoil,
            aim_pitch_offset: 0.0,
            aim_yaw_offset: 0.0,
            sustained_fire_time: 0.0,
            last_fire_time: -1e9,
        }
    }

    /// 是否可以開火
    pub fn can_fire(&self, now: f64) -> bool {
        !self.reloading && now >= self.next_fire_time && self.mag > 0
    }

    /// 嘗試開火：消耗彈藥、推進後座力、設定冷卻。回傳是否成功。
    pub fn attempt_fire(&mut self, now: f64) -> bool {
        if !self.can_fire(now) {
            return false;
        }
        self.mag -= 1;
        let (p, y) = self.recoil.fire(now);
        self.aim_pitch_offset += p;
        self.aim_yaw_offset += y;

        // Odin 旋轉加速：持續開火時射速提升（12→15.6 rps）
        let mut fire_rate = self.stats.fire_rate_rps;
        if self.stats.key == "odin" {
            let gap = now - self.last_fire_time;
            if gap < 0.3 {
                // 連續開火中
                self.sustained_fire_time += gap;
                // 0~1.5s 線性加速到 1.3 倍
                let boost = 1.0 + (self.sustained_fire_time / 1.5).min(1.0) * 0.3;
                fire_rate = self.stats.fire_rate_rps * boost;
            } else {
                self.sustained_fire_time = 0.0;
            }
            self.last_fire_time = now;
        }
        self.next_fire_time = now + 1.0 / fire_rate;

        if self.mag == 0 {
            self.start_reload(now);
        }
        true
    }

    /// 開始換彈
    pub fn start_reload(&mut self, now: f64) -> bool {
        if self.reloading || self.mag >= self.stats.mag_size || self.reserve == 0 {
            return false;
        }
        let _ = now;
        self.reloading = true;
        self.reload_progress = 0.0;
        true
    }

    /// 每 tick 更新（後座力恢復 + 換彈進度）
    pub fn update(&mut self, now: f64, dt: f64) {
        self.recoil.update(now, dt);
        if self.reloading {
            self.reload_progress += dt;
            if self.reload_progress >= self.stats.reload_time {
                let need = self.stats.mag_size - self.mag;
                let take = need.min(self.reserve);
                self.mag += take;
                self.reserve -= take;
                self.reloading = false;
            }
        }
    }

    /// 重設彈藥到滿
    pub fn reset_ammo(&mut self) {
        self.mag = self.stats.mag_size;
        self.reserve = self.stats.reserve;
        self.reloading = false;
        self.reload_progress = 0.0;
    }

    /// 換彈進度 byte（0-254 = 進度%，255 = 未換彈）
    pub fn reload_progress_byte(&self) -> u8 {
        if !self.reloading {
            255
        } else {
            let frac = (self.reload_progress / self.stats.reload_time.max(1e-9)).min(1.0);
            (frac * 254.0).max(0.0).min(254.0) as u8
        }
    }
}
