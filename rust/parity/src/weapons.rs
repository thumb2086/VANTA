/// weapons.rs — M4 武器資料庫（對齊 Python server/game/weapons.py）
///
/// 所有數值為「開放專案的近似值」（Riot 未公開精確參數），
/// 集中在資料表以利日後校正。

/// 傷害衰減
#[derive(Debug, Clone, Copy)]
pub struct DamageFalloff {
    pub range_min: f64,
    pub range_max: f64,
    pub dmg_max: f64,
    pub dmg_min: f64,
}

/// 武器資料
#[derive(Debug, Clone, Copy)]
pub struct WeaponStats {
    pub key: &'static str,
    pub name: &'static str,
    pub wclass: &'static str,       // sidearm/smg/rifle/sniper/shotgun/heavy/melee
    pub price: u16,
    pub fire_rate_rps: f64,
    pub mag_size: u32,
    pub reserve: u32,
    pub reload_time: f64,
    pub damage: f64,
    pub falloff: Option<DamageFalloff>,
    pub penetration_level: i32,
    pub first_shot_accuracy_deg: f64,
    pub spread_per_bullet: f64,
    pub move_speed_mult: f64,
    pub ads_spread_mult: f64,
    pub automatic: bool,
    pub burst: u32,
    pub pellets: u32,
    pub scoped: bool,
}

/// 依距離計算傷害（無衰減則恆定）
pub fn damage_at(stats: &WeaponStats, dist: f64) -> f64 {
    match stats.falloff {
        None => stats.damage,
        Some(f) => {
            if dist <= f.range_min {
                f.dmg_max
            } else if dist >= f.range_max {
                f.dmg_min
            } else {
                let t = (dist - f.range_min) / (f.range_max - f.range_min);
                f.dmg_max + (f.dmg_min - f.dmg_max) * t
            }
        }
    }
}

/// 依 key 查武器（找不到回傳 None）
pub fn weapon(key: &str) -> Option<&'static WeaponStats> {
    WEAPONS.iter().find(|w| w.key == key)
}

/// 全部武器資料表
pub static WEAPONS: &[WeaponStats] = &[
    // --- 手槍 (sidearm) ---
    WeaponStats { key: "classic", name: "Classic", wclass: "sidearm", price: 0,
        fire_rate_rps: 6.75, mag_size: 12, reserve: 60, reload_time: 1.5,
        damage: 26.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.2, spread_per_bullet: 0.02,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: true,
        burst: 3, pellets: 1, scoped: false },
    WeaponStats { key: "ghost", name: "Ghost", wclass: "sidearm", price: 500,
        fire_rate_rps: 6.75, mag_size: 15, reserve: 45, reload_time: 1.5,
        damage: 30.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.2, spread_per_bullet: 0.02,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "bandit", name: "Bandit", wclass: "sidearm", price: 600,
        fire_rate_rps: 4.0, mag_size: 8, reserve: 24, reload_time: 1.5,
        damage: 40.0, falloff: Some(DamageFalloff { range_min: 20.0, range_max: 50.0, dmg_max: 40.0, dmg_min: 30.0 }),
        penetration_level: 1, first_shot_accuracy_deg: 0.25, spread_per_bullet: 0.015,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: false,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "sheriff", name: "Sheriff", wclass: "sidearm", price: 800,
        fire_rate_rps: 4.0, mag_size: 6, reserve: 18, reload_time: 2.0,
        damage: 55.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.3, spread_per_bullet: 0.01,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: false,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "frenzy", name: "Frenzy", wclass: "sidearm", price: 450,
        fire_rate_rps: 10.0, mag_size: 13, reserve: 39, reload_time: 1.5,
        damage: 26.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.5, spread_per_bullet: 0.03,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "shorty", name: "Shorty", wclass: "sidearm", price: 300,
        fire_rate_rps: 3.3, mag_size: 2, reserve: 10, reload_time: 1.0,
        damage: 12.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.9, spread_per_bullet: 0.1,
        move_speed_mult: 1.0, ads_spread_mult: 0.85, automatic: false,
        burst: 1, pellets: 12, scoped: false },
    // --- 衝鋒槍 (smg) ---
    WeaponStats { key: "stinger", name: "Stinger", wclass: "smg", price: 1100,
        fire_rate_rps: 18.0, mag_size: 20, reserve: 60, reload_time: 1.8,
        damage: 27.0, falloff: Some(DamageFalloff { range_min: 20.0, range_max: 50.0, dmg_max: 27.0, dmg_min: 22.0 }),
        penetration_level: 1, first_shot_accuracy_deg: 0.6, spread_per_bullet: 0.05,
        move_speed_mult: 0.98, ads_spread_mult: 0.6, automatic: false,
        burst: 4, pellets: 1, scoped: false },
    WeaponStats { key: "spectre", name: "Spectre", wclass: "smg", price: 1600,
        fire_rate_rps: 13.33, mag_size: 30, reserve: 90, reload_time: 2.1,
        damage: 26.0, falloff: Some(DamageFalloff { range_min: 15.0, range_max: 30.0, dmg_max: 26.0, dmg_min: 20.0 }),
        penetration_level: 1, first_shot_accuracy_deg: 0.5, spread_per_bullet: 0.04,
        move_speed_mult: 0.98, ads_spread_mult: 0.6, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    // --- 步槍 (rifle) ---
    WeaponStats { key: "bulldog", name: "Bulldog", wclass: "rifle", price: 2050,
        fire_rate_rps: 9.15, mag_size: 24, reserve: 72, reload_time: 2.5,
        damage: 35.0, falloff: Some(DamageFalloff { range_min: 30.0, range_max: 50.0, dmg_max: 35.0, dmg_min: 31.0 }),
        penetration_level: 2, first_shot_accuracy_deg: 0.25, spread_per_bullet: 0.03,
        move_speed_mult: 0.95, ads_spread_mult: 0.55, automatic: false,
        burst: 3, pellets: 1, scoped: false },
    WeaponStats { key: "guardian", name: "Guardian", wclass: "rifle", price: 2250,
        fire_rate_rps: 6.5, mag_size: 12, reserve: 36, reload_time: 2.5,
        damage: 65.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.2, spread_per_bullet: 0.02,
        move_speed_mult: 0.92, ads_spread_mult: 0.55, automatic: false,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "phantom", name: "Phantom", wclass: "rifle", price: 2900,
        fire_rate_rps: 11.0, mag_size: 30, reserve: 90, reload_time: 2.5,
        damage: 39.0, falloff: Some(DamageFalloff { range_min: 15.0, range_max: 50.0, dmg_max: 39.0, dmg_min: 31.0 }),
        penetration_level: 2, first_shot_accuracy_deg: 0.2, spread_per_bullet: 0.04,
        move_speed_mult: 0.95, ads_spread_mult: 0.55, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "vandal", name: "Vandal", wclass: "rifle", price: 2900,
        fire_rate_rps: 9.75, mag_size: 25, reserve: 75, reload_time: 2.5,
        damage: 40.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.25, spread_per_bullet: 0.05,
        move_speed_mult: 0.95, ads_spread_mult: 0.55, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    // --- 狙擊 (sniper) ---
    WeaponStats { key: "marshal", name: "Marshal", wclass: "sniper", price: 950,
        fire_rate_rps: 1.5, mag_size: 5, reserve: 15, reload_time: 2.5,
        damage: 101.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.15, spread_per_bullet: 0.01,
        move_speed_mult: 0.90, ads_spread_mult: 0.35, automatic: false,
        burst: 1, pellets: 1, scoped: true },
    WeaponStats { key: "outlaw", name: "Outlaw", wclass: "sniper", price: 2400,
        fire_rate_rps: 1.2, mag_size: 5, reserve: 15, reload_time: 3.0,
        damage: 140.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.1, spread_per_bullet: 0.01,
        move_speed_mult: 0.80, ads_spread_mult: 0.30, automatic: false,
        burst: 1, pellets: 1, scoped: true },
    WeaponStats { key: "operator", name: "Operator", wclass: "sniper", price: 4700,
        fire_rate_rps: 0.75, mag_size: 5, reserve: 15, reload_time: 3.7,
        damage: 150.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.05, spread_per_bullet: 0.01,
        move_speed_mult: 0.70, ads_spread_mult: 0.25, automatic: false,
        burst: 1, pellets: 1, scoped: true },
    // --- 霰彈 (shotgun) ---
    WeaponStats { key: "bucky", name: "Bucky", wclass: "shotgun", price: 850,
        fire_rate_rps: 1.1, mag_size: 5, reserve: 15, reload_time: 2.5,
        damage: 20.0, falloff: Some(DamageFalloff { range_min: 8.0, range_max: 20.0, dmg_max: 20.0, dmg_min: 8.0 }),
        penetration_level: 1, first_shot_accuracy_deg: 0.8, spread_per_bullet: 0.1,
        move_speed_mult: 0.96, ads_spread_mult: 0.6, automatic: false,
        burst: 1, pellets: 15, scoped: false },
    WeaponStats { key: "judge", name: "Judge", wclass: "shotgun", price: 1850,
        fire_rate_rps: 3.5, mag_size: 7, reserve: 21, reload_time: 2.2,
        damage: 17.0, falloff: Some(DamageFalloff { range_min: 10.0, range_max: 20.0, dmg_max: 17.0, dmg_min: 7.0 }),
        penetration_level: 1, first_shot_accuracy_deg: 0.9, spread_per_bullet: 0.1,
        move_speed_mult: 0.95, ads_spread_mult: 0.6, automatic: true,
        burst: 1, pellets: 12, scoped: false },
    // --- 重武器 (heavy) ---
    WeaponStats { key: "ares", name: "Ares", wclass: "heavy", price: 1600,
        fire_rate_rps: 13.0, mag_size: 50, reserve: 150, reload_time: 4.2,
        damage: 30.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.4, spread_per_bullet: 0.05,
        move_speed_mult: 0.85, ads_spread_mult: 0.55, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    WeaponStats { key: "odin", name: "Odin", wclass: "heavy", price: 3200,
        fire_rate_rps: 12.0, mag_size: 100, reserve: 300, reload_time: 5.0,
        damage: 38.0, falloff: None, penetration_level: 2,
        first_shot_accuracy_deg: 0.5, spread_per_bullet: 0.06,
        move_speed_mult: 0.80, ads_spread_mult: 0.55, automatic: true,
        burst: 1, pellets: 1, scoped: false },
    // --- 近戰 ---
    WeaponStats { key: "knife", name: "Knife", wclass: "melee", price: 0,
        fire_rate_rps: 1.5, mag_size: 1, reserve: 0, reload_time: 0.0,
        damage: 50.0, falloff: None, penetration_level: 0,
        first_shot_accuracy_deg: 0.0, spread_per_bullet: 0.0,
        move_speed_mult: 1.0, ads_spread_mult: 1.0, automatic: false,
        burst: 1, pellets: 1, scoped: false },
];
