/// inventory.rs — 武器槽位與切換（對齊 Python server/game/inventory.py）
///
/// 《特戰英豪》式武器配置：主武器(0) / 副武器(1) / 近戰刀(2)。
/// 切換立即生效（快照可即時反映），但切換期間不可開火（switch_time 門控）

use super::weapons::WeaponStats;

/// 武器槽位（3-slot system）
#[derive(Debug, Clone)]
pub struct WeaponInventory {
    /// 每個槽位的武器 stats（None = 該槽位空）
    pub slots: [Option<&'static WeaponStats>; 3],
    /// 目前使用的槽位
    pub active: usize,
    /// 切換完成後才可開火的世界時間
    pub switch_until: f64,
}

impl WeaponInventory {
    /// 建立預設武器庫：無主武器、Classic 手槍、Knife
    pub fn new() -> Self {
        use super::weapons::weapon;
        Self {
            slots: [
                None,                          // 主武器（可購買）
                weapon("classic"),             // 副武器（預設手槍）
                weapon("knife"),               // 近戰
            ],
            active: 1,
            switch_until: -1.0,
        }
    }

    /// 取得目前使用中的武器 stats
    pub fn active_stats(&self) -> Option<&'static WeaponStats> {
        self.slots[self.active]
    }

    /// 切換到指定槽位的時間（刀 0.45s，其他 0.65s）
    pub fn switch_duration(&self, slot: usize) -> f64 {
        if slot == 2 { 0.45 } else { 0.65 }
    }

    /// 切換到指定槽位（立即生效，切換期間不可開火）
    pub fn start_switch(&mut self, slot: usize, now: f64) -> bool {
        if slot >= 3 || self.slots[slot].is_none() {
            return false;
        }
        if slot == self.active {
            return false;
        }
        self.active = slot;
        self.switch_until = now + self.switch_duration(slot);
        true
    }

    /// 是否正在切換中
    pub fn switching(&self, now: f64) -> bool {
        now < self.switch_until
    }

    /// 安裝主武器
    pub fn install_primary(&mut self, stats: &'static WeaponStats) {
        self.slots[0] = Some(stats);
    }

    /// 重設所有彈藥
    pub fn reset_all(&mut self) {
        // 注意：實際 reset 需要 WeaponState，這裡只處理 slot 邏輯
        // WeaponState 的 reset 在呼叫端處理
    }
}
