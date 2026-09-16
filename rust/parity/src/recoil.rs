//! RecoilController — 對齊 server/game/recoil.py
//! 固定後座力圖案 + 種子化隨機 yaw + 恢復延遲（步進式恢復）。

use crate::mt19937::MT19937;

pub struct RecoilPattern {
    pub pitch_deg: &'static [f64],
    pub yaw_deg: &'static [f64],
    pub protected_bullets: u32,
    pub reset_time: f64,
    pub recover_rate: f64,
    pub random_yaw_scale: f64,
}

// Vandal 圖案（與 recoil.py PATTERNS["vandal"] 一致）
pub static VANDAL: RecoilPattern = RecoilPattern {
    pitch_deg: &[
        1.1, 2.0, 2.7, 2.4, 2.0, 1.5, 1.1, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.35, 0.3, 0.3, 0.3,
        0.25, 0.25, 0.2,
    ],
    yaw_deg: &[
        0.0, 0.0, 0.0, 0.35, 0.55, 0.25, -0.45, -0.65, -0.3, 0.5, 0.85, 0.4, -0.6, -0.9, 0.2,
        0.6, 0.3, -0.5, 0.4, 0.2,
    ],
    protected_bullets: 6,
    reset_time: 0.7,
    recover_rate: 6.0,
    random_yaw_scale: 0.6,
};

fn clamp(v: f64, lo: f64, hi: f64) -> f64 {
    if v < lo {
        lo
    } else if v > hi {
        hi
    } else {
        v
    }
}

pub struct RecoilController {
    pattern: &'static RecoilPattern,
    rng: MT19937,
    pub bullet_index: u32,
    pub pitch: f64,
    pub yaw: f64,
    last_fire_time: f64,
    pub shots_fired: u32,
}

impl RecoilController {
    pub fn new(pattern: &'static RecoilPattern, seed: u32) -> Self {
        RecoilController {
            pattern,
            rng: MT19937::new(seed),
            bullet_index: 0,
            pitch: 0.0,
            yaw: 0.0,
            last_fire_time: -1e9,
            shots_fired: 0,
        }
    }

    pub fn fire(&mut self, now: f64) -> (f64, f64) {
        let i = self.bullet_index as usize;
        let p = self.pattern.pitch_deg[i.min(self.pattern.pitch_deg.len() - 1)];
        let y;
        if i < self.pattern.yaw_deg.len() && (i as u32) < self.pattern.protected_bullets {
            y = self.pattern.yaw_deg[i];
        } else {
            let base = if self.pattern.yaw_deg.is_empty() {
                0.0
            } else {
                self.pattern.yaw_deg[i.min(self.pattern.yaw_deg.len() - 1)]
            };
            y = base + self.rng.uniform(-self.pattern.random_yaw_scale, self.pattern.random_yaw_scale);
        }
        self.bullet_index += 1;
        self.shots_fired += 1;
        self.last_fire_time = now;
        self.pitch += p;
        self.yaw += y;
        (p, y)
    }

    pub fn update(&mut self, now: f64, dt: f64) {
        if now - self.last_fire_time > self.pattern.reset_time {
            let step = self.pattern.recover_rate * dt;
            if self.pitch.abs() <= step {
                self.pitch = 0.0;
            } else {
                self.pitch = clamp(self.pitch - step.copysign(self.pitch), -90.0, 90.0);
            }
            if self.yaw.abs() <= step {
                self.yaw = 0.0;
            } else {
                self.yaw = clamp(self.yaw - step.copysign(self.yaw), -90.0, 90.0);
            }
        }
    }

    /// 換彈後圖案回到第 1 發（對齊 Python `reset_pattern`）
    pub fn reset_pattern(&mut self) {
        self.bullet_index = 0;
    }

    pub fn fully_recovered(&self) -> bool {
        self.pitch.abs() < 1e-9 && self.yaw.abs() < 1e-9
    }
}
