//! Collision — 對齊 server/game/collision.py（位元組級行為）
//! 圓柱 vs AABB 推離、天花板、玩家配對推離、空間雜湊寬相位。
//! 運算順序與 Python 完全相同 → 結果位元組一致。

use crate::ballistics::Vec3;
use std::collections::HashMap;

pub const PLAYER_RADIUS: f64 = 0.35;
pub const PLAYER_HEIGHT: f64 = 1.8;
pub const COLLISION_PASSES: usize = 3;

#[derive(Clone, Copy)]
pub struct Wall {
    pub mn: Vec3,
    pub mx: Vec3,
}

// 對齊 collision._push_out
fn push_out(x: f64, z: f64, r: f64, wall: &Wall) -> Option<(f64, f64, f64)> {
    let (mnx, mxx) = (wall.mn.x, wall.mx.x);
    let (mnz, mxz) = (wall.mn.z, wall.mx.z);
    let cx = if x < mnx { mnx } else if x > mxx { mxx } else { x };
    let cz = if z < mnz { mnz } else if z > mxz { mxz } else { z };
    let (dx, dz) = (x - cx, z - cz);
    let d2 = dx * dx + dz * dz;
    if d2 >= r * r - 1e-12 {
        return None;
    }
    if d2 > 1e-12 {
        let d = d2.sqrt();
        let push = r - d;
        return Some((dx / d, dz / d, push));
    }
    // 圓心在 AABB 內：四向最小位移
    let cands = [
        ((mnx - r) - x, -1.0f64, 0.0f64),
        ((mxx + r) - x, 1.0f64, 0.0f64),
        ((mnz - r) - z, 0.0f64, -1.0f64),
        ((mxz + r) - z, 0.0f64, 1.0f64),
    ];
    let mut best = cands[0];
    for c in &cands[1..] {
        if c.0.abs() < best.0.abs() {
            best = *c;
        }
    }
    Some((best.1, best.2, best.0.abs()))
}

pub fn resolve_player_wall(pos: &mut Vec3, vel: &mut Vec3, wall: &Wall) -> bool {
    let y = pos.y;
    if y + PLAYER_HEIGHT <= wall.mn.y || y >= wall.mx.y {
        return false;
    }
    match push_out(pos.x, pos.z, PLAYER_RADIUS, wall) {
        None => false,
        Some((nx, nz, push)) => {
            pos.x += nx * push;
            pos.z += nz * push;
            let vn = vel.x * nx + vel.z * nz;
            if vn < 0.0 {
                vel.x -= vn * nx;
                vel.z -= vn * nz;
            }
            true
        }
    }
}

pub fn resolve_ceiling(pos: &mut Vec3, vel: &mut Vec3, wall: &Wall) -> bool {
    let head = pos.y + PLAYER_HEIGHT;
    if head <= wall.mx.y || pos.y >= wall.mx.y {
        return false;
    }
    if pos.x + PLAYER_RADIUS <= wall.mn.x
        || pos.x - PLAYER_RADIUS >= wall.mx.x
        || pos.z + PLAYER_RADIUS <= wall.mn.z
        || pos.z - PLAYER_RADIUS >= wall.mx.z
    {
        return false;
    }
    pos.y = wall.mx.y - PLAYER_HEIGHT;
    if vel.y > 0.0 {
        vel.y = 0.0;
    }
    true
}

pub fn resolve_player_player(a_pos: &mut Vec3, a_vel: &mut Vec3,
                             b_pos: &mut Vec3, b_vel: &mut Vec3) -> bool {
    let mut dx = b_pos.x - a_pos.x;
    let mut dz = b_pos.z - a_pos.z;
    let d2 = dx * dx + dz * dz;
    let min_d = 2.0 * PLAYER_RADIUS;
    if d2 >= min_d * min_d {
        return false;
    }
    let d;
    if d2 < 1e-12 {
        dx = 1.0;
        dz = 0.0;
        d = 0.0;
    } else {
        d = d2.sqrt();
        dx /= d;
        dz /= d;
    }
    let half = (min_d - d) * 0.5;
    a_pos.x -= dx * half;
    a_pos.z -= dz * half;
    b_pos.x += dx * half;
    b_pos.z += dz * half;
    // 消除「接近方向」相對速度
    let vrel = (a_vel.x - b_vel.x) * dx + (a_vel.z - b_vel.z) * dz;
    if vrel > 0.0 {
        a_vel.x -= vrel * dx;
        a_vel.z -= vrel * dz;
        b_vel.x += vrel * dx;
        b_vel.z += vrel * dz;
    }
    true
}

// --------------------------------------------------------------------- //
// 空間雜湊（對齊 collision.WallSpatialHash：cell=4.0、原索引排序、固定格子順序）
// --------------------------------------------------------------------- //
pub struct SpatialHash {
    cell: f64,
    walls: Vec<Wall>,
    grid: HashMap<(i32, i32), Vec<usize>>,
}

impl SpatialHash {
    pub fn new(walls: Vec<Wall>) -> Self {
        let cell = 4.0f64;
        let mut grid: HashMap<(i32, i32), Vec<usize>> = HashMap::new();
        for (idx, w) in walls.iter().enumerate() {
            let mnx = ((w.mn.x - PLAYER_RADIUS) / cell).floor() as i32;
            let mxx = ((w.mx.x + PLAYER_RADIUS) / cell).floor() as i32;
            let mnz = ((w.mn.z - PLAYER_RADIUS) / cell).floor() as i32;
            let mxz = ((w.mx.z + PLAYER_RADIUS) / cell).floor() as i32;
            for cx in mnx..=mxx {
                for cz in mnz..=mxz {
                    grid.entry((cx, cz)).or_default().push(idx);
                }
            }
        }
        for v in grid.values_mut() {
            v.sort_unstable();
        }
        SpatialHash { cell, walls, grid }
    }

    pub fn all_walls(&self) -> &[Wall] {
        &self.walls
    }

    pub fn query(&self, x: f64, z: f64, radius: f64) -> Vec<&Wall> {
        let cx0 = ((x - radius) / self.cell).floor() as i32;
        let cx1 = ((x + radius) / self.cell).floor() as i32;
        let cz0 = ((z - radius) / self.cell).floor() as i32;
        let cz1 = ((z + radius) / self.cell).floor() as i32;
        let mut out = Vec::new();
        for cx in cx0..=cx1 {
            for cz in cz0..=cz1 {
                if let Some(idxs) = self.grid.get(&(cx, cz)) {
                    for &idx in idxs {
                        out.push(&self.walls[idx]);
                    }
                }
            }
        }
        out
    }
}

// --------------------------------------------------------------------- //
// 世界級解析（對齊 collision.resolve_world）
// --------------------------------------------------------------------- //
pub fn resolve_world(pos: &mut [Vec3], vel: &mut [Vec3], alive: &[bool], hash: &SpatialHash) {
    let n = pos.len();
    for _ in 0..COLLISION_PASSES {
        let mut moved = false;
        for i in 0..n {
            if !alive[i] {
                continue;
            }
            for wall in hash.query(pos[i].x, pos[i].z, PLAYER_RADIUS) {
                moved |= resolve_player_wall(&mut pos[i], &mut vel[i], wall);
            }
            for wall in hash.query(pos[i].x, pos[i].z, PLAYER_RADIUS) {
                moved |= resolve_ceiling(&mut pos[i], &mut vel[i], wall);
            }
        }
        for i in 0..n {
            if !alive[i] {
                continue;
            }
            for j in (i + 1)..n {
                if !alive[j] {
                    continue;
                }
                // AABB 早退
                let dx = pos[j].x - pos[i].x;
                if dx > 2.0 * PLAYER_RADIUS || dx < -2.0 * PLAYER_RADIUS {
                    continue;
                }
                let dz = pos[j].z - pos[i].z;
                if dz > 2.0 * PLAYER_RADIUS || dz < -2.0 * PLAYER_RADIUS {
                    continue;
                }
                let (mut ap, mut av, mut bp, mut bv) =
                    (pos[i], vel[i], pos[j], vel[j]);
                if resolve_player_player(&mut ap, &mut av, &mut bp, &mut bv) {
                    pos[i] = ap;
                    vel[i] = av;
                    pos[j] = bp;
                    vel[j] = bv;
                    moved = true;
                }
            }
        }
        if !moved {
            break;
        }
    }
}
