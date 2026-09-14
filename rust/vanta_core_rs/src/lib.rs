//! vanta_core_rs — Python C 擴展：把 Rust 核心（movement/recoil/ballistics）
//! 暴露給 Python 伺服器，零物件建立、無 GC 的熱路徑。
//!
//! 建置：cd rust/vanta_core_rs && cargo build --release
//! 產出：target/release/libvanta_core_rs.so → 複製到 server/core/_rust/
//! Python 載入：server/core/rs_bridge.py（找不到擴展時回退純 Python）

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use vanta_parity::ballistics as ball;
use vanta_parity::movement as mov;
use vanta_parity::recoil as rcl;

// --------------------------------------------------------------------- //
// MovementController
// --------------------------------------------------------------------- //
#[pyclass]
pub struct MovementController {
    inner: mov::MovementController,
}

fn cfg_from_dict(d: Option<&Bound<'_, PyDict>>) -> PyResult<mov::Config> {
    let mut c = mov::Config::default();
    if let Some(dict) = d {
        macro_rules! getf {
            ($k:literal, $f:ident) => {
                if let Some(v) = dict.get_item($k)? {
                    c.$f = v.extract::<f64>()?;
                }
            };
        }
        getf!("run_speed", run_speed);
        getf!("walk_ratio", walk_ratio);
        getf!("crouch_ratio", crouch_ratio);
        getf!("jump_speed", jump_speed);
        getf!("gravity", gravity);
        getf!("ground_accel", ground_accel);
        getf!("ground_friction", ground_friction);
        getf!("opposite_decel", opposite_decel);
        getf!("air_accel", air_accel);
        getf!("air_speed_ratio", air_speed_ratio);
        getf!("jump_buffer_time", jump_buffer_time);
        getf!("jump_coyote_time", jump_coyote_time);
    }
    Ok(c)
}

#[pymethods]
impl MovementController {
    #[new]
    #[pyo3(signature = (cfg_dict=None, ground_y=0.0))]
    fn new(cfg_dict: Option<&Bound<'_, PyDict>>, ground_y: f64) -> PyResult<Self> {
        Ok(MovementController {
            inner: mov::MovementController::new(cfg_from_dict(cfg_dict)?, ground_y),
        })
    }

    #[pyo3(signature = (forward, strafe, walk, crouch, jump, dt, speed_mult=1.0))]
    fn step(&mut self, forward: f64, strafe: f64, walk: bool, crouch: bool,
            jump: bool, dt: f64, speed_mult: f64) {
        self.inner.step(forward, strafe, walk, crouch, jump, dt, speed_mult);
    }

    #[getter]
    fn pos(&self) -> (f64, f64, f64) {
        (self.inner.pos.x, self.inner.pos.y, self.inner.pos.z)
    }
    #[getter]
    fn vel(&self) -> (f64, f64, f64) {
        (self.inner.vel.x, self.inner.vel.y, self.inner.vel.z)
    }
    fn set_pos(&mut self, x: f64, y: f64, z: f64) {
        self.inner.pos = ball::Vec3::new(x, y, z);
    }
    fn set_vel(&mut self, x: f64, y: f64, z: f64) {
        self.inner.vel = ball::Vec3::new(x, y, z);
    }
    #[getter]
    fn on_ground(&self) -> bool {
        self.inner.on_ground
    }
    #[getter]
    fn crouching(&self) -> bool {
        self.inner.crouching
    }
    #[getter]
    fn walking(&self) -> bool {
        self.inner.walking
    }
    #[getter]
    fn time_since_land(&self) -> f64 {
        self.inner.time_since_land
    }
    fn current_max_speed(&self) -> f64 {
        self.inner.current_max_speed()
    }
    fn horizontal_speed(&self) -> f64 {
        self.inner.horizontal_speed()
    }
    fn speed_ratio(&self) -> f64 {
        self.inner.speed_ratio()
    }
}

// --------------------------------------------------------------------- //
// MovementBatch — 批次移動（一次跨邊界處理 N 玩家 × 多步）
// 關鍵：細粒度單步跨邊界（每 tick 每玩家一次 pyo3 呼叫）有固定開銷，
//       批次化把邊界成本攤平，才是 pyo3 橋接的正確用法。
// --------------------------------------------------------------------- //
#[pyclass]
pub struct MovementBatch {
    inner: Vec<mov::MovementController>,
}

#[pymethods]
impl MovementBatch {
    #[new]
    #[pyo3(signature = (cfg_dict=None, ground_y=0.0, count=10))]
    fn new(cfg_dict: Option<&Bound<'_, PyDict>>, ground_y: f64, count: usize) -> PyResult<Self> {
        let cfg = cfg_from_dict(cfg_dict)?;
        Ok(MovementBatch {
            inner: (0..count)
                .map(|_| mov::MovementController::new(cfg, ground_y))
                .collect(),
        })
    }

    /// 一次推進 N 玩家。輸入為等長 list（fwd/str/walk/crouch/jump/speed_mult）。
    #[pyo3(signature = (fwd, strafe, walk, crouch, jump, speed_mult, dt))]
    fn step_all(&mut self, fwd: Vec<f64>, strafe: Vec<f64>, walk: Vec<bool>,
                crouch: Vec<bool>, jump: Vec<bool>, speed_mult: Vec<f64>, dt: f64) -> PyResult<()> {
        let n = self.inner.len();
        if fwd.len() != n || strafe.len() != n || walk.len() != n || crouch.len() != n
            || jump.len() != n || speed_mult.len() != n {
            return Err(PyValueError::new_err("輸入清單長度必須等於玩家數"));
        }
        for i in 0..n {
            self.inner[i].step(fwd[i], strafe[i], walk[i], crouch[i], jump[i], dt, speed_mult[i]);
        }
        Ok(())
    }

    fn positions(&self) -> Vec<(f64, f64, f64)> {
        self.inner.iter().map(|c| (c.pos.x, c.pos.y, c.pos.z)).collect()
    }
    fn velocities(&self) -> Vec<(f64, f64, f64)> {
        self.inner.iter().map(|c| (c.vel.x, c.vel.y, c.vel.z)).collect()
    }
    fn set_state(&mut self, i: usize, px: f64, py: f64, pz: f64, vx: f64, vy: f64, vz: f64) {
        if i < self.inner.len() {
            self.inner[i].pos = ball::Vec3::new(px, py, pz);
            self.inner[i].vel = ball::Vec3::new(vx, vy, vz);
        }
    }
}

// --------------------------------------------------------------------- //
// WorldSim — 世界迴圈 Rust 化（M4）：一次跨邊界完成 移動 + 碰撞
// Python 端每 tick 傳入所有輸入 → 取回玩家狀態（每 tick 僅 4 次跨邊界）
// --------------------------------------------------------------------- //
#[pyclass]
pub struct WorldSim {
    ctrls: Vec<mov::MovementController>,
    hash: vanta_parity::collision::SpatialHash,
    count: usize,
}

#[pymethods]
impl WorldSim {
    #[new]
    #[pyo3(signature = (walls, cfg_dict=None, ground_y=0.0, count=10))]
    fn new(walls: Vec<(f64, f64, f64, f64, f64, f64)>,
           cfg_dict: Option<&Bound<'_, PyDict>>, ground_y: f64, count: usize) -> PyResult<Self> {
        let cfg = cfg_from_dict(cfg_dict)?;
        let ws: Vec<vanta_parity::collision::Wall> = walls
            .iter()
            .map(|(ax, ay, az, bx, by, bz)| vanta_parity::collision::Wall {
                mn: ball::Vec3::new(*ax, *ay, *az),
                mx: ball::Vec3::new(*bx, *by, *bz),
            })
            .collect();
        Ok(WorldSim {
            ctrls: (0..count)
                .map(|_| mov::MovementController::new(cfg, ground_y))
                .collect(),
            hash: vanta_parity::collision::SpatialHash::new(ws),
            count,
        })
    }

    /// 每 tick 從 Python 同步玩家狀態（重生/回彈/外部修改被尊重）。
    /// Python 是「位置權威」；Rust 是加速計算引擎（內部計時器連續累積）。
    fn sync_states(&mut self, pos: Vec<(f64, f64, f64)>, vel: Vec<(f64, f64, f64)>) {
        let n = self.count.min(pos.len()).min(vel.len());
        for i in 0..n {
            self.ctrls[i].pos = ball::Vec3::new(pos[i].0, pos[i].1, pos[i].2);
            self.ctrls[i].vel = ball::Vec3::new(vel[i].0, vel[i].1, vel[i].2);
        }
    }

    /// 一次推進完整世界 tick（移動 → 碰撞）。輸入皆為等長 list（count 個）。
    #[pyo3(signature = (fwd, strafe, walk, crouch, jump, speed_mult, alive, dt, movable))]
    fn step_all(&mut self, fwd: Vec<f64>, strafe: Vec<f64>, walk: Vec<bool>,
                crouch: Vec<bool>, jump: Vec<bool>, speed_mult: Vec<f64>,
                alive: Vec<bool>, dt: f64, movable: bool) -> PyResult<()> {
        let n = self.count;
        if fwd.len() != n || strafe.len() != n || walk.len() != n || crouch.len() != n
            || jump.len() != n || speed_mult.len() != n || alive.len() != n {
            return Err(PyValueError::new_err("輸入清單長度必須等於玩家數"));
        }
        // 1) 移動
        for i in 0..n {
            let c = &mut self.ctrls[i];
            if !alive[i] {
                c.vel = ball::Vec3::ZERO;
                continue;
            }
            if movable {
                c.step(fwd[i], strafe[i], walk[i], crouch[i], jump[i], dt, speed_mult[i]);
            } else {
                // 買期/結算：原地煞車（Python step_movement(None)）
                c.step(0.0, 0.0, false, false, false, dt, speed_mult[i]);
            }
        }
        // 2) 碰撞（空間雜湊 + 玩家配對，3 passes）
        let mut pos: Vec<ball::Vec3> = self.ctrls.iter().map(|c| c.pos).collect();
        let mut vel: Vec<ball::Vec3> = self.ctrls.iter().map(|c| c.vel).collect();
        vanta_parity::collision::resolve_world(&mut pos, &mut vel, &alive, &self.hash);
        for i in 0..n {
            self.ctrls[i].pos = pos[i];
            self.ctrls[i].vel = vel[i];
        }
        Ok(())
    }

    fn positions(&self) -> Vec<(f64, f64, f64)> {
        self.ctrls.iter().map(|c| (c.pos.x, c.pos.y, c.pos.z)).collect()
    }
    fn velocities(&self) -> Vec<(f64, f64, f64)> {
        self.ctrls.iter().map(|c| (c.vel.x, c.vel.y, c.vel.z)).collect()
    }
    fn on_grounds(&self) -> Vec<bool> {
        self.ctrls.iter().map(|c| c.on_ground).collect()
    }
    fn crouchings(&self) -> Vec<bool> {
        self.ctrls.iter().map(|c| c.crouching).collect()
    }
    fn walkings(&self) -> Vec<bool> {
        self.ctrls.iter().map(|c| c.walking).collect()
    }
    fn time_since_lands(&self) -> Vec<f64> {
        self.ctrls.iter().map(|c| c.time_since_land).collect()
    }
}

// --------------------------------------------------------------------- //
// RecoilController（Vandal 圖案 + 種子化 RNG）
// --------------------------------------------------------------------- //
#[pyclass]
pub struct RecoilController {
    inner: rcl::RecoilController,
}

#[pymethods]
impl RecoilController {
    #[new]
    #[pyo3(signature = (seed=42))]
    fn new(seed: u32) -> Self {
        RecoilController {
            inner: rcl::RecoilController::new(&rcl::VANDAL, seed),
        }
    }

    fn fire(&mut self, now: f64) -> (f64, f64) {
        self.inner.fire(now)
    }
    fn update(&mut self, now: f64, dt: f64) {
        self.inner.update(now, dt);
    }
    #[getter]
    fn pitch(&self) -> f64 {
        self.inner.pitch
    }
    #[getter]
    fn yaw(&self) -> f64 {
        self.inner.yaw
    }
    #[getter]
    fn bullet_index(&self) -> u32 {
        self.inner.bullet_index
    }
    #[getter]
    fn shots_fired(&self) -> u32 {
        self.inner.shots_fired
    }
}

// --------------------------------------------------------------------- //
// Ballistics：resolve_hitscan（純函式）
//  players: [(feet_x, feet_y, feet_z, alive, health)]
//  walls:   [(mn_x, mn_y, mn_z, mx_x, mx_y, mx_z, material)]
//  回傳 hit 清單 [(slot, region(0頭/1身/2腿), base, dealt, wall_hits)]
// --------------------------------------------------------------------- //
#[pyfunction]
#[pyo3(signature = (players, walls, shooter, origin, target, damage, pen_level, max_dist=150.0))]
fn resolve_hitscan(
    players: Vec<(f64, f64, f64, bool, f64)>,
    walls: Vec<(f64, f64, f64, f64, f64, f64, u8)>,
    shooter: usize,
    origin: (f64, f64, f64),
    target: (f64, f64, f64),
    damage: f64,
    pen_level: i32,
    max_dist: f64,
) -> PyResult<Vec<(i32, u8, f64, f64, i32)>> {
    if shooter >= players.len() {
        return Err(PyValueError::new_err("shooter 超出玩家數"));
    }
    let ents: Vec<ball::Entity> = players
        .iter()
        .map(|(x, y, z, alive, hp)| ball::Entity {
            feet: ball::Vec3::new(*x, *y, *z),
            alive: *alive,
            health: *hp,
        })
        .collect();
    let ws: Vec<ball::Wall> = walls
        .iter()
        .map(|(ax, ay, az, bx, by, bz, m)| ball::Wall {
            mn: ball::Vec3::new(*ax, *ay, *az),
            mx: ball::Vec3::new(*bx, *by, *bz),
            material: *m,
        })
        .collect();
    let mut scene = ball::Scene { walls: ws, players: ents };
    let o = ball::Vec3::new(origin.0, origin.1, origin.2);
    let dir = ball::Vec3::new(target.0 - origin.0, target.1 - origin.1, target.2 - origin.2);
    let dir = dir.normalized();
    let res = ball::resolve_hitscan(
        &mut scene,
        shooter,
        o,
        dir,
        damage,
        pen_level,
        max_dist,
    );
    Ok(res
        .hits
        .into_iter()
        .map(|h| (h.slot, h.region, h.base, h.dealt, h.wall_hits))
        .collect())
}

// --------------------------------------------------------------------- //
#[pymodule]
fn vanta_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MovementController>()?;
    m.add_class::<MovementBatch>()?;
    m.add_class::<WorldSim>()?;
    m.add_class::<RecoilController>()?;
    m.add_function(wrap_pyfunction!(resolve_hitscan, m)?)?;
    Ok(())
}
