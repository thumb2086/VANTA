//! Movement — 對齊 server/core/movement.py（含 speed_mult 狀態修正）
//! 由 parity 黃金資料位元組級驗證；pyo3 橋接共用此實作。

use crate::ballistics::Vec3;

pub const EPSILON: f64 = 1e-12;

#[derive(Clone, Copy)]
pub struct Config {
    pub run_speed: f64,
    pub walk_ratio: f64,
    pub crouch_ratio: f64,
    pub jump_speed: f64,
    pub gravity: f64,
    pub ground_accel: f64,
    pub ground_friction: f64,
    pub opposite_decel: f64,
    pub air_accel: f64,
    pub air_speed_ratio: f64,
    pub jump_buffer_time: f64,
    pub jump_coyote_time: f64,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            run_speed: 5.4,
            walk_ratio: 0.54,
            crouch_ratio: 0.43,
            jump_speed: 4.15,
            gravity: 11.5,
            ground_accel: 22.0,
            ground_friction: 24.0,
            opposite_decel: 45.0,
            air_accel: 26.0,
            air_speed_ratio: 1.0,
            jump_buffer_time: 0.10,
            jump_coyote_time: 0.10,
        }
    }
}

pub struct MovementController {
    pub cfg: Config,
    pub pos: Vec3,
    pub vel: Vec3,
    pub on_ground: bool,
    pub crouching: bool,
    pub walking: bool,
    pub ads: bool,
    pub time_since_land: f64,
    ground_y: f64,
    jump_buffer: f64,
    coyote: f64,
}

impl MovementController {
    pub fn new(cfg: Config, ground_y: f64) -> Self {
        MovementController {
            cfg,
            pos: Vec3::new(0.0, ground_y, 0.0),
            vel: Vec3::ZERO,
            on_ground: true,
            crouching: false,
            walking: false,
            ads: false,
            time_since_land: 999.0,
            ground_y,
            jump_buffer: 0.0,
            coyote: 0.0,
        }
    }

    pub fn current_max_speed(&self) -> f64 {
        let mut v = if self.crouching {
            self.cfg.run_speed * self.cfg.crouch_ratio
        } else if self.walking {
            self.cfg.run_speed * self.cfg.walk_ratio
        } else {
            self.cfg.run_speed
        };
        if self.ads {
            v *= 0.76;
        }
        v
    }

    pub fn horizontal_speed(&self) -> f64 {
        self.vel.horizontal().length()
    }

    pub fn speed_ratio(&self) -> f64 {
        let r = self.horizontal_speed() / self.cfg.run_speed;
        if r < 0.0 {
            0.0
        } else if r > 1.0 {
            1.0
        } else {
            r
        }
    }

    /// 對齊 movement.py step：tick 順序完全相同；speed_mult 作用於最大速度。
    pub fn step(&mut self, forward: f64, strafe: f64, walk: bool, crouch: bool,
                jump: bool, ads: bool, dt: f64, speed_mult: f64) {
        // 1) 計時器
        self.jump_buffer = (self.jump_buffer - dt).max(0.0);
        self.coyote = (self.coyote - dt).max(0.0);
        if jump {
            self.jump_buffer = self.cfg.jump_buffer_time;
        }
        // 2) 姿態
        self.crouching = crouch;
        self.walking = walk;
        self.ads = ads;
        // 3) 水平移動
        let mut move_dir = Vec3::new(strafe, 0.0, forward);
        if move_dir.length_sq() > EPSILON {
            move_dir = move_dir.normalized();
        }
        if self.on_ground {
            self.coyote = self.cfg.jump_coyote_time;
            self.ground_move(move_dir, dt, speed_mult);
        } else {
            self.air_move(move_dir, dt, speed_mult);
        }
        // 4) 重力
        if !self.on_ground {
            self.vel.y -= self.cfg.gravity * dt;
        }
        // 5) 跳躍
        if self.on_ground && self.jump_buffer > 0.0 {
            self.vel.y = self.cfg.jump_speed;
            self.on_ground = false;
            self.jump_buffer = 0.0;
        }
        // 6) 積分
        self.pos = self.pos.add(self.vel.mul(dt));
        // 7) 地面夾取（含落地計時語意）
        if self.pos.y <= self.ground_y && self.vel.y <= 0.0 {
            let was_airborne = !self.on_ground;
            if was_airborne {
                self.time_since_land = 0.0;
            } else {
                self.time_since_land += dt;
            }
            self.pos.y = self.ground_y;
            self.vel.y = 0.0;
            self.on_ground = true;
        } else {
            self.time_since_land += dt;
        }
    }

    fn ground_move(&mut self, move_dir: Vec3, dt: f64, speed_mult: f64) {
        let max_speed = self.current_max_speed() * speed_mult;
        let hvel = self.vel.horizontal();
        let new_h;
        if move_dir.length_sq() > EPSILON {
            let decel = if hvel.length_sq() > EPSILON
                && hvel.normalized().dot(move_dir) < -0.3
            {
                self.cfg.opposite_decel
            } else {
                self.cfg.ground_accel
            };
            new_h = approach_vec(hvel, move_dir.mul(max_speed), decel * dt);
        } else {
            new_h = approach_vec(hvel, Vec3::ZERO, self.cfg.ground_friction * dt);
        }
        let new_h = if new_h.length_sq() > max_speed * max_speed {
            new_h.normalized().mul(max_speed)
        } else {
            new_h
        };
        self.vel.x = new_h.x;
        self.vel.z = new_h.z;
    }

    fn air_move(&mut self, move_dir: Vec3, dt: f64, speed_mult: f64) {
        let max_speed = self.cfg.run_speed * self.cfg.air_speed_ratio * speed_mult;
        let hvel = self.vel.horizontal();
        let new_h = approach_vec(hvel, move_dir.mul(max_speed), self.cfg.air_accel * dt);
        self.vel.x = new_h.x;
        self.vel.z = new_h.z;
    }
}

fn approach_vec(v: Vec3, target: Vec3, max_delta: f64) -> Vec3 {
    let diff = target.sub(v);
    let dist = diff.length();
    if dist <= max_delta || dist < EPSILON {
        target
    } else {
        v.add(diff.mul(max_delta / dist))
    }
}
