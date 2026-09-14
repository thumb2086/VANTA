/// abilities.rs — M10-12/M15 技能框架（對齊 Python server/game/abilities.py）
///
/// 技能類型、定義、實例、冷卻/充能系統。
/// 每位玩家由 AbilitySystem 管理四個技能槽 (C/Q/E/X)。

use crate::status::{StatusKind, StatusEffectSystem};

// ──────────────────────────────────────────────────────────────────────
// 技能類型列舉
// ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum AbilityType {
    Flash = 0,
    Frag = 1,
    Smoke = 2,
    Trap = 3,
    Heal = 4,
    Wall = 5,
    Slow = 6,
    Nearsight = 7,
    Suppression = 8,
    Teleport = 9,
    Beam = 10,
    StimBeacon = 11,
}

// ──────────────────────────────────────────────────────────────────────
// 技能槽位
// ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AbilitySlot {
    C = 0,
    Q = 1,
    E = 2,
    X = 3,
}

// ──────────────────────────────────────────────────────────────────────
// 技能靜態定義（不可變，所有同類型實例共用）
// ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub struct AbilityDef {
    pub name: &'static str,
    pub agent: &'static str,
    pub slot: AbilitySlot,
    pub ability_type: AbilityType,
    pub cooldown: f64,
    pub charges: u32,
    pub duration: f64,
    pub radius: f64,
    pub damage: f64,
    pub description: &'static str,
}

// ──────────────────────────────────────────────────────────────────────
// 技能運行時實例（每位玩家各有一份）
// ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AbilityInstance {
    pub def: AbilityDef,
    pub slot_idx: usize,
    pub current_charges: u32,
    pub last_used_time: f64,
    pub active_effects: Vec<ActiveEffect>,
}

#[derive(Debug, Clone)]
pub struct ActiveEffect {
    pub kind: StatusKind,
    pub time_left: f64,
    pub potency: f64,
}

impl AbilityInstance {
    pub fn new(def: AbilityDef, slot_idx: usize) -> Self {
        Self {
            def,
            slot_idx,
            current_charges: def.charges,
            last_used_time: 0.0,
            active_effects: Vec::new(),
        }
    }

    /// 是否可以使用：有充能 且 冷卻歸零
    pub fn can_use(&self, current_time: f64) -> bool {
        self.current_charges > 0 && self.last_used_time + self.def.cooldown <= current_time
    }

    /// 嘗試使用技能，成功回傳 true
    pub fn use_ability(&mut self, current_time: f64) -> bool {
        if !self.can_use(current_time) {
            return false;
        }
        self.current_charges -= 1;
        self.last_used_time = current_time;
        true
    }

    /// 重設充能（回合開始時呼叫）
    pub fn reset_charges(&mut self) {
        self.current_charges = self.def.charges;
        self.last_used_time = 0.0;
        self.active_effects.clear();
    }
}

// ──────────────────────────────────────────────────────────────────────
// 技能系統（管理一位玩家的四個技能槽）
// ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AbilitySystem {
    pub abilities: Vec<AbilityInstance>,
    pub suppressed: bool,
}

impl AbilitySystem {
    pub fn new(defs: &[AbilityDef]) -> Self {
        let abilities = defs
            .iter()
            .enumerate()
            .map(|(i, &d)| AbilityInstance::new(d, i))
            .collect();
        Self {
            abilities,
            suppressed: false,
        }
    }

    /// 指定索引的技能是否可用
    pub fn can_use(&self, index: usize, current_time: f64) -> bool {
        if self.suppressed {
            return false;
        }
        self.abilities
            .get(index)
            .map(|a| a.can_use(current_time))
            .unwrap_or(false)
    }

    /// 使用指定索引的技能
    pub fn use_ability(&mut self, index: usize, current_time: f64) -> bool {
        if self.suppressed {
            return false;
        }
        self.abilities
            .get_mut(index)
            .map(|a| a.use_ability(current_time))
            .unwrap_or(false)
    }

    /// 每 tick 更新冷卻計時與活躍效果
    pub fn update_cooldowns(&mut self, dt: f64, statuses: &mut StatusEffectSystem) {
        for ab in &mut self.abilities {
            ab.active_effects.retain_mut(|e| {
                e.time_left -= dt;
                if e.time_left <= 0.0 {
                    false
                } else {
                    statuses.apply(e.kind, e.time_left, e.potency);
                    true
                }
            });
        }
    }

    /// 重設所有技能充能（回合開始）
    pub fn reset_charges(&mut self) {
        for ab in &mut self.abilities {
            ab.reset_charges();
        }
        self.suppressed = false;
    }

    /// 技能快照（供客戶端顯示）
    pub fn snapshot(&self) -> Vec<AbilitySnapshot> {
        self.abilities
            .iter()
            .map(|a| AbilitySnapshot {
                name: a.def.name,
                slot: a.def.slot,
                charges: a.current_charges,
                max_charges: a.def.charges,
                cooldown: a.def.cooldown,
                can_use: false, // 由呼叫端填入
            })
            .collect()
    }
}

#[derive(Debug, Clone)]
pub struct AbilitySnapshot {
    pub name: &'static str,
    pub slot: AbilitySlot,
    pub charges: u32,
    pub max_charges: u32,
    pub cooldown: f64,
    pub can_use: bool,
}

// ──────────────────────────────────────────────────────────────────────
// 特務靜態定義
// ──────────────────────────────────────────────────────────────────────

pub struct AgentAbilities;

impl AgentAbilities {
    /// 依特務 key 回傳四個技能定義 (C, Q, E, X)
    pub fn for_agent(agent: &str) -> Vec<AbilityDef> {
        match agent {
            "jett" => Self::jett(),
            "sage" => Self::sage(),
            "brimstone" => Self::brimstone(),
            _ => Vec::new(),
        }
    }

    fn jett() -> Vec<AbilityDef> {
        vec![
            // C: Cloudburst — 投出小型煙霧球，落地後展開
            AbilityDef {
                name: "cloudburst",
                agent: "jett",
                slot: AbilitySlot::C,
                ability_type: AbilityType::Smoke,
                cooldown: 8.0,
                charges: 3,
                duration: 7.0,
                radius: 2.5,
                damage: 0.0,
                description: "投出小型煙霧球，落地後快速展開",
            },
            // Q: Updraft — 瞬間向上跳躍
            AbilityDef {
                name: "updraft",
                agent: "jett",
                slot: AbilitySlot::Q,
                ability_type: AbilityType::Teleport, // 最接近：垂直位移
                cooldown: 10.0,
                charges: 2,
                duration: 0.0,
                radius: 0.0,
                damage: 0.0,
                description: "瞬間向上跳躍",
            },
            // E: Tailwind — 瞬間水平衝刺
            AbilityDef {
                name: "tailwind",
                agent: "jett",
                slot: AbilitySlot::E,
                ability_type: AbilityType::Teleport,
                cooldown: 6.0,
                charges: 2,
                duration: 0.4,
                radius: 0.0,
                damage: 0.0,
                description: "瞬間水平衝刺",
            },
            // X: Blade Storm — 投擲飛刀
            AbilityDef {
                name: "blade_storm",
                agent: "jett",
                slot: AbilitySlot::X,
                ability_type: AbilityType::Beam,
                cooldown: 0.0,
                charges: 5,
                duration: 0.0,
                radius: 0.6,
                damage: 50.0,
                description: "投出多把飛刀，每把造成傷害",
            },
        ]
    }

    fn sage() -> Vec<AbilityDef> {
        vec![
            // C: Slow Orb — 減速球
            AbilityDef {
                name: "slow_orb",
                agent: "sage",
                slot: AbilitySlot::C,
                ability_type: AbilityType::Slow,
                cooldown: 15.0,
                charges: 2,
                duration: 5.0,
                radius: 4.0,
                damage: 0.0,
                description: "投出後在落地點生成減速區域",
            },
            // Q: Barrier Orb — 冰牆
            AbilityDef {
                name: "barrier_orb",
                agent: "sage",
                slot: AbilitySlot::Q,
                ability_type: AbilityType::Wall,
                cooldown: 30.0,
                charges: 1,
                duration: 15.0,
                radius: 0.0,
                damage: 0.0,
                description: "在瞄準方向升起一道牆壁，阻擋視線和移動",
            },
            // E: Healing Orb — 治療球
            AbilityDef {
                name: "healing_orb",
                agent: "sage",
                slot: AbilitySlot::E,
                ability_type: AbilityType::Heal,
                cooldown: 15.0,
                charges: 1,
                duration: 3.0,
                radius: 0.0,
                damage: 0.0,
                description: "對自身或範圍內友方恢復生命",
            },
            // X: Resurrection — 復活
            AbilityDef {
                name: "resurrection",
                agent: "sage",
                slot: AbilitySlot::X,
                ability_type: AbilityType::Heal,
                cooldown: 0.0,
                charges: 1,
                duration: 0.0,
                radius: 0.0,
                damage: 0.0,
                description: "復活一名已死亡的隊友至施法者旁",
            },
        ]
    }

    fn brimstone() -> Vec<AbilityDef> {
        vec![
            // C: Stim Beacon — 刺激信標
            AbilityDef {
                name: "stim_beacon",
                agent: "brimstone",
                slot: AbilitySlot::C,
                ability_type: AbilityType::StimBeacon,
                cooldown: 15.0,
                charges: 1,
                duration: 8.0,
                radius: 4.0,
                damage: 0.0,
                description: "在地面放置信標，範圍內友方獲得加速",
            },
            // Q: Incendiary — 燃燒彈
            AbilityDef {
                name: "incendiary",
                agent: "brimstone",
                slot: AbilitySlot::Q,
                ability_type: AbilityType::Frag, // 近似
                cooldown: 20.0,
                charges: 1,
                duration: 6.0,
                radius: 3.0,
                damage: 40.0,
                description: "投出後在落地點生成火焰區域，持續扣血",
            },
            // E: Sky Smoke — 空投煙霧
            AbilityDef {
                name: "sky_smoke",
                agent: "brimstone",
                slot: AbilitySlot::E,
                ability_type: AbilityType::Smoke,
                cooldown: 12.0,
                charges: 2,
                duration: 14.0,
                radius: 3.5,
                damage: 0.0,
                description: "在瞄準方向遠處投放煙霧",
            },
            // X: Orbital Strike — 軌道打擊
            AbilityDef {
                name: "orbital_strike",
                agent: "brimstone",
                slot: AbilitySlot::X,
                ability_type: AbilityType::Beam,
                cooldown: 0.0,
                charges: 1,
                duration: 2.0,
                radius: 5.0,
                damage: 150.0,
                description: "在指定區域延遲後造成範圍致死傷害",
            },
        ]
    }
}

// ──────────────────────────────────────────────────────────────────────
// 建構快捷函式
// ──────────────────────────────────────────────────────────────────────

/// 依特務 key 建立 AbilitySystem（回合開始時呼叫）
pub fn build_agent_system(agent: &str) -> AbilitySystem {
    let defs = AgentAbilities::for_agent(agent);
    AbilitySystem::new(&defs)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jett_has_4_abilities() {
        let defs = AgentAbilities::for_agent("jett");
        assert_eq!(defs.len(), 4);
        assert_eq!(defs[0].name, "cloudburst");
        assert_eq!(defs[1].name, "updraft");
        assert_eq!(defs[2].name, "tailwind");
        assert_eq!(defs[3].name, "blade_storm");
    }

    #[test]
    fn sage_has_4_abilities() {
        let defs = AgentAbilities::for_agent("sage");
        assert_eq!(defs.len(), 4);
        assert_eq!(defs[2].ability_type, AbilityType::Heal);
    }

    #[test]
    fn brimstone_has_4_abilities() {
        let defs = AgentAbilities::for_agent("brimstone");
        assert_eq!(defs.len(), 4);
        assert_eq!(defs[0].ability_type, AbilityType::StimBeacon);
    }

    #[test]
    fn unknown_agent_returns_empty() {
        assert!(AgentAbilities::for_agent("unknown").is_empty());
    }

    #[test]
    fn can_use_requires_charges_and_cooldown() {
        let defs = AgentAbilities::for_agent("jett");
        let sys = AbilitySystem::new(&defs);
        // 有充能、冷卻為 0 → 可用
        assert!(sys.can_use(0, 100.0));
    }

    #[test]
    fn use_ability_decrements_charges() {
        let defs = AgentAbilities::for_agent("jett");
        let mut sys = AbilitySystem::new(&defs);
        assert!(sys.use_ability(0, 100.0));
        assert_eq!(sys.abilities[0].current_charges, 2); // 3 - 1
    }

    #[test]
    fn suppression_blocks_ability() {
        let defs = AgentAbilities::for_agent("jett");
        let mut sys = AbilitySystem::new(&defs);
        sys.suppressed = true;
        assert!(!sys.can_use(0, 100.0));
        assert!(!sys.use_ability(0, 100.0));
    }

    #[test]
    fn reset_charges_restores_all() {
        let defs = AgentAbilities::for_agent("jett");
        let mut sys = AbilitySystem::new(&defs);
        sys.use_ability(0, 100.0);
        sys.use_ability(0, 200.0);
        sys.use_ability(0, 300.0);
        assert_eq!(sys.abilities[0].current_charges, 0);
        sys.reset_charges();
        assert_eq!(sys.abilities[0].current_charges, 3);
    }
}
