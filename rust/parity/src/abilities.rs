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
// AbilityEffect — 完整的技能效果資料
// ──────────────────────────────────────────────────────────────────────

/// 每個技能施放後產生的效果，包含渲染和遊戲邏輯所需的全部資料。
/// 客戶端根據 effect_type 決定渲染方式，伺服端用於碰撞/傷害判定。
#[derive(Debug, Clone)]
pub enum AbilityEffect {
    /// 煙霧球： LOS 阻斷器
    Smoke {
        center: [f64; 3],
        radius: f64,
        duration: f64,
        team: u8,
    },
    /// 閃光： 白屏致盲
    Flash {
        center: [f64; 3],
        direction: [f64; 3],
        radius: f64,
    },
    /// 碎片爆炸： 範圍傷害 + 粒子
    Frag {
        center: [f64; 3],
        radius: f64,
        damage: f64,
    },
    /// 治療： 綠色粒子 + HP 恢復
    Heal {
        target_slot: u32,
        amount: f64,
        team: u8,
    },
    /// 部署牆： 阻擋視線和移動
    Wall {
        start: [f64; 3],
        end: [f64; 3],
        duration: f64,
        team: u8,
    },
    /// 減速區： 地面冰霜效果 + SLOW
    Slow {
        center: [f64; 3],
        radius: f64,
        duration: f64,
        potency: f64,
    },
    /// 陷阱： 可見發光指示器
    Trap {
        center: [f64; 3],
        radius: f64,
        team: u8,
    },
    /// 傳送門： 雙端 portal + 連接光束
    Teleport {
        from: [f64; 3],
        to: [f64; 3],
        duration: f64,
    },
    /// 近視： 暗霧覆蓋
    Nearsight {
        center: [f64; 3],
        radius: f64,
        duration: f64,
    },
    /// 技能封鎖： 電流特效
    Suppression {
        target_slot: u32,
        duration: f64,
    },
    /// 線性光束： 穿透傷害
    Beam {
        origin: [f64; 3],
        direction: [f64; 3],
        length: f64,
        damage: f64,
        radius: f64,
    },
    /// 刺激信標： 範圍加速
    StimBeacon {
        center: [f64; 3],
        radius: f64,
        duration: f64,
        team: u8,
    },
}

impl AbilityEffect {
    /// 回傳效果類型名稱（供序列化 / 客戶端路由）
    pub fn effect_type(&self) -> &'static str {
        match self {
            AbilityEffect::Smoke { .. } => "smoke",
            AbilityEffect::Flash { .. } => "flash",
            AbilityEffect::Frag { .. } => "frag",
            AbilityEffect::Heal { .. } => "heal",
            AbilityEffect::Wall { .. } => "wall",
            AbilityEffect::Slow { .. } => "slow_zone",
            AbilityEffect::Trap { .. } => "trap",
            AbilityEffect::Teleport { .. } => "teleport",
            AbilityEffect::Nearsight { .. } => "nearsight",
            AbilityEffect::Suppression { .. } => "suppression",
            AbilityEffect::Beam { .. } => "beam",
            AbilityEffect::StimBeacon { .. } => "trap",
        }
    }
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

    /// 根據技能定義產生對應的 AbilityEffect。
    /// caster_pos / aim_dir 為施法者位置和瞄準方向。
    pub fn create_effect(
        &self,
        caster_pos: [f64; 3],
        aim_dir: [f64; 3],
        team: u8,
    ) -> AbilityEffect {
        match self.def.name {
            // ─── Jett ───
            "cloudburst" => {
                let land = [
                    caster_pos[0] + aim_dir[0] * 5.0,
                    0.5,
                    caster_pos[2] + aim_dir[2] * 5.0,
                ];
                AbilityEffect::Smoke {
                    center: land,
                    radius: self.def.radius,
                    duration: self.def.duration,
                    team,
                }
            }
            "updraft" => {
                // Vertical launch — no world effect, just impulse
                AbilityEffect::Teleport {
                    from: caster_pos,
                    to: [
                        caster_pos[0],
                        caster_pos[1] + 6.0,
                        caster_pos[2],
                    ],
                    duration: 0.4,
                }
            }
            "tailwind" => {
                let dest = [
                    caster_pos[0] + aim_dir[0] * 8.0,
                    caster_pos[1],
                    caster_pos[2] + aim_dir[2] * 8.0,
                ];
                AbilityEffect::Teleport {
                    from: caster_pos,
                    to: dest,
                    duration: 0.4,
                }
            }
            "blade_storm" => AbilityEffect::Frag {
                center: caster_pos,
                radius: 0.6,
                damage: self.def.damage,
            },
            // ─── Sage ───
            "slow_orb" => {
                let land = [
                    caster_pos[0] + aim_dir[0] * 6.0,
                    0.1,
                    caster_pos[2] + aim_dir[2] * 6.0,
                ];
                AbilityEffect::Slow {
                    center: land,
                    radius: self.def.radius,
                    duration: self.def.duration,
                    potency: 1.0,
                }
            }
            "barrier_orb" | "barrier_wall" => {
                let center = [
                    caster_pos[0] + aim_dir[0] * 2.5,
                    caster_pos[1],
                    caster_pos[2] + aim_dir[2] * 2.5,
                ];
                let perp = if (aim_dir[0] * aim_dir[0] + aim_dir[2] * aim_dir[2]) > 0.01 {
                    let len = (aim_dir[0] * aim_dir[0] + aim_dir[2] * aim_dir[2]).sqrt();
                    [-aim_dir[2] / len, 0.0, aim_dir[0] / len]
                } else {
                    [1.0, 0.0, 0.0]
                };
                let half = 2.5;
                let start = [
                    center[0] - perp[0] * half,
                    0.0,
                    center[2] - perp[2] * half,
                ];
                let end = [
                    center[0] + perp[0] * half,
                    self.def.radius, // reused as wall height
                    center[2] + perp[2] * half,
                ];
                AbilityEffect::Wall {
                    start,
                    end,
                    duration: self.def.duration,
                    team,
                }
            }
            "healing_orb" => AbilityEffect::Heal {
                target_slot: 0, // filled by server based on target
                amount: 60.0,
                team,
            },
            "resurrection" => AbilityEffect::Heal {
                target_slot: 0, // filled by server
                amount: 100.0,
                team,
            },
            // ─── Brimstone ───
            "stim_beacon" => AbilityEffect::StimBeacon {
                center: caster_pos,
                radius: self.def.radius,
                duration: self.def.duration,
                team,
            },
            "incendiary" => {
                let land = [
                    caster_pos[0] + aim_dir[0] * 8.0,
                    0.1,
                    caster_pos[2] + aim_dir[2] * 8.0,
                ];
                AbilityEffect::Frag {
                    center: land,
                    radius: self.def.radius,
                    damage: self.def.damage,
                }
            }
            "sky_smoke" => {
                let target = [
                    caster_pos[0] + aim_dir[0] * 15.0,
                    0.0,
                    caster_pos[2] + aim_dir[2] * 15.0,
                ];
                AbilityEffect::Smoke {
                    center: target,
                    radius: self.def.radius,
                    duration: self.def.duration,
                    team,
                }
            }
            "orbital_strike" => {
                let target = [
                    caster_pos[0] + aim_dir[0] * 12.0,
                    0.0,
                    caster_pos[2] + aim_dir[2] * 12.0,
                ];
                AbilityEffect::Frag {
                    center: target,
                    radius: self.def.radius,
                    damage: self.def.damage,
                }
            }
            // ─── Generic fallback ───
            _ => match self.def.ability_type {
                AbilityType::Smoke => AbilityEffect::Smoke {
                    center: [
                        caster_pos[0] + aim_dir[0] * 5.0,
                        0.5,
                        caster_pos[2] + aim_dir[2] * 5.0,
                    ],
                    radius: self.def.radius,
                    duration: self.def.duration,
                    team,
                },
                AbilityType::Frag => AbilityEffect::Frag {
                    center: caster_pos,
                    radius: self.def.radius,
                    damage: self.def.damage,
                },
                AbilityType::Heal => AbilityEffect::Heal {
                    target_slot: 0,
                    amount: 50.0,
                    team,
                },
                AbilityType::Wall => AbilityEffect::Wall {
                    start: caster_pos,
                    end: [
                        caster_pos[0] + aim_dir[0] * 5.0,
                        3.0,
                        caster_pos[2] + aim_dir[2] * 5.0,
                    ],
                    duration: self.def.duration,
                    team,
                },
                AbilityType::Slow => AbilityEffect::Slow {
                    center: [
                        caster_pos[0] + aim_dir[0] * 5.0,
                        0.1,
                        caster_pos[2] + aim_dir[2] * 5.0,
                    ],
                    radius: self.def.radius,
                    duration: self.def.duration,
                    potency: 1.0,
                },
                AbilityType::Teleport => AbilityEffect::Teleport {
                    from: caster_pos,
                    to: [
                        caster_pos[0] + aim_dir[0] * 6.0,
                        caster_pos[1],
                        caster_pos[2] + aim_dir[2] * 6.0,
                    ],
                    duration: 0.5,
                },
                AbilityType::Beam => AbilityEffect::Beam {
                    origin: caster_pos,
                    direction: aim_dir,
                    length: 50.0,
                    damage: self.def.damage,
                    radius: 1.5,
                },
                _ => AbilityEffect::Frag {
                    center: caster_pos,
                    radius: 1.0,
                    damage: 0.0,
                },
            },
        }
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
