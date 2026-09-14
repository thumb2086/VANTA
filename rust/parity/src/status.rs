/// status.rs — M13 狀態干擾 (Debuffs)（對齊 Python server/game/status.py）
///
/// 十種狀態：BLIND/CONCUSS/VULNERABLE/SPEED_BOOST/NEARSIGHT/SUPPRESSED/DECAY/SLOW/DEAFENED/REVEALED
/// 疊加規則：同型態以「剩餘時間最長」者勝出，potency 取最高。

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum StatusKind {
    Blind = 0,
    Concuss = 1,
    Vulnerable = 2,
    SpeedBoost = 3,
    Nearsight = 4,
    Suppressed = 5,
    Decay = 6,
    Slow = 7,
    Deafened = 8,
    Revealed = 9,
}

impl StatusKind {
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "blind" => Some(Self::Blind),
            "concuss" => Some(Self::Concuss),
            "vulnerable" => Some(Self::Vulnerable),
            "speed_boost" => Some(Self::SpeedBoost),
            "nearsight" => Some(Self::Nearsight),
            "suppressed" => Some(Self::Suppressed),
            "decay" => Some(Self::Decay),
            "slow" => Some(Self::Slow),
            "deafened" => Some(Self::Deafened),
            "revealed" => Some(Self::Revealed),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ActiveStatus {
    pub kind: StatusKind,
    pub time_left: f64,
    pub potency: f64,
}

#[derive(Debug, Clone)]
pub struct StatusEffectSystem {
    statuses: Vec<ActiveStatus>,
}

impl StatusEffectSystem {
    pub fn new() -> Self {
        Self { statuses: Vec::new() }
    }

    /// 套用狀態（同型態以長者勝出、potency 取最高）
    pub fn apply(&mut self, kind: StatusKind, duration: f64, potency: f64) {
        for s in &mut self.statuses {
            if s.kind == kind {
                s.time_left = s.time_left.max(duration);
                s.potency = s.potency.max(potency);
                return;
            }
        }
        self.statuses.push(ActiveStatus { kind, time_left: duration, potency });
    }

    /// 每 tick 更新
    pub fn update(&mut self, dt: f64) {
        for s in &mut self.statuses {
            s.time_left -= dt;
        }
        self.statuses.retain(|s| s.time_left > 0.0);
    }

    /// 是否擁有某狀態
    pub fn has(&self, kind: StatusKind) -> bool {
        self.statuses.iter().any(|s| s.kind == kind)
    }

    /// 取某狀態的 potency（無則 0.0）
    pub fn potency(&self, kind: StatusKind) -> f64 {
        self.statuses.iter()
            .find(|s| s.kind == kind)
            .map(|s| s.potency)
            .unwrap_or(0.0)
    }

    /// 移動速度倍率：暈眩→0.65；減速→×0.5；加速→×(1+0.25×potency)
    pub fn move_speed_mult(&self) -> f64 {
        let mut base = 1.0;
        if self.has(StatusKind::Concuss) {
            base *= 0.65;
        }
        if self.has(StatusKind::Slow) {
            base *= 0.5;
        }
        let boost = 1.0 + 0.25 * self.potency(StatusKind::SpeedBoost);
        base * boost
    }

    /// 受傷倍率：易傷→×(1+potency)
    pub fn damage_taken_mult(&self) -> f64 {
        1.0 + self.potency(StatusKind::Vulnerable)
    }

    /// 是否可開火（被閃瞎時不可）
    pub fn can_shoot(&self) -> bool {
        !self.has(StatusKind::Blind)
    }

    /// 是否可使用技能（被封鎖時不可）
    pub fn can_use_ability(&self) -> bool {
        !self.has(StatusKind::Suppressed)
    }

    /// 視野是否被遮蔽
    pub fn sight_blocked(&self) -> bool {
        self.has(StatusKind::Blind)
    }

    /// Decay 每秒持續傷害量
    pub fn decay_dps(&self) -> f64 {
        if self.has(StatusKind::Decay) {
            self.potency(StatusKind::Decay)
        } else {
            0.0
        }
    }

    /// 清空所有狀態
    pub fn clear(&mut self) {
        self.statuses.clear();
    }
}
