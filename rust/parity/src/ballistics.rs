//! Ballistics — 對齊 server/game/ballistics.py + geometry.py
//! Hitbox（頭 4x / 身 1x / 腿 0.85x 膠囊）、牆面 AABB、穿透衰減、跨發狀態（傷害/死亡/溢傷）。

use std::f64;

pub const EPSILON: f64 = 1e-12;
pub const HEAD_MULT: f64 = 4.0;
pub const BODY_MULT: f64 = 1.0;
pub const LEGS_MULT: f64 = 0.85;
pub const MAX_DIST: f64 = 150.0;
pub const MAX_PENETRATIONS: usize = 2;
pub const N_PLAYERS: usize = 10;

#[derive(Clone, Copy, Debug)]
pub struct Vec3 {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Vec3 {
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Vec3 { x, y, z }
    }
    pub fn add(self, o: Vec3) -> Vec3 {
        Vec3::new(self.x + o.x, self.y + o.y, self.z + o.z)
    }
    pub fn sub(self, o: Vec3) -> Vec3 {
        Vec3::new(self.x - o.x, self.y - o.y, self.z - o.z)
    }
    pub fn mul(self, s: f64) -> Vec3 {
        Vec3::new(self.x * s, self.y * s, self.z * s)
    }
    pub fn dot(self, o: Vec3) -> f64 {
        self.x * o.x + self.y * o.y + self.z * o.z
    }
    pub fn length_sq(self) -> f64 {
        self.x * self.x + self.y * self.y + self.z * self.z
    }
    pub fn length(self) -> f64 {
        self.length_sq().sqrt()
    }
    pub fn normalized(self) -> Vec3 {
        let l = self.length();
        if l < EPSILON {
            Vec3::ZERO
        } else {
            Vec3::new(self.x / l, self.y / l, self.z / l)
        }
    }
    pub fn horizontal(self) -> Vec3 {
        Vec3::new(self.x, 0.0, self.z)
    }
    pub const ZERO: Vec3 = Vec3 { x: 0.0, y: 0.0, z: 0.0 };
}

// --------------------------------------------------------------------- //
// 牆面 / 材質
// --------------------------------------------------------------------- //
#[derive(Clone, Copy)]
pub struct Wall {
    pub mn: Vec3,
    pub mx: Vec3,
    pub material: u8, // 0=concrete 1=wood 2=metal 3=unbreakable
}

fn material_req(mat: u8) -> i32 {
    match mat {
        0 => 2, // concrete: PENETRATION_MEDIUM
        1 => 1, // wood:     PENETRATION_LIGHT
        2 => 2, // metal:    PENETRATION_MEDIUM
        3 => 4, // unbreakable: HEAVY+1
        _ => 4,
    }
}

fn material_keep(mat: u8) -> f64 {
    match mat {
        0 => 0.5,
        1 => 0.8,
        2 => 0.6,
        _ => 0.0,
    }
}

// --------------------------------------------------------------------- //
// 射線 vs 球 / 膠囊 / AABB（對齊 geometry.py）
// --------------------------------------------------------------------- //
pub fn ray_vs_sphere(origin: Vec3, dir: Vec3, center: Vec3, radius: f64, max_dist: f64) -> Option<f64> {
    let oc = origin.sub(center);
    let a = dir.dot(dir);
    let b = 2.0 * oc.dot(dir);
    let c = oc.dot(oc) - radius * radius;
    let disc = b * b - 4.0 * a * c;
    if disc < 0.0 {
        return None;
    }
    let sq = disc.sqrt();
    let t1 = (-b - sq) / (2.0 * a);
    let t2 = (-b + sq) / (2.0 * a);
    let t = if t1 >= 0.0 { t1 } else { t2 };
    if t >= 0.0 && t <= max_dist {
        Some(t)
    } else {
        None
    }
}

pub fn ray_vs_capsule(origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, radius: f64, max_dist: f64) -> Option<f64> {
    let axis = b.sub(a);
    let length = axis.length();
    if length < EPSILON {
        return ray_vs_sphere(origin, dir, a, radius, max_dist);
    }
    let u = axis.mul(1.0 / length);
    // 正確的射線-軸最近推導：W = origin - a
    // t_c = [(W·u)(d·u) - W·d] / (1-(d·u)^2)，d 為單位向量
    let d = dir.normalized();
    let w = origin.sub(a);
    let c = d.dot(u);
    let denom = 1.0 - c * c;
    let mut t0: Option<f64> = None;
    if denom > 1e-9 {
        let tc = ((w.dot(u)) * c - w.dot(d)) / denom;
        let closest = origin.add(d.mul(tc));
        let proj = closest.dot(u) - a.dot(u);
        if proj >= 0.0 && proj <= length {
            let perp = closest.sub(a.add(u.mul(proj)));
            let d2 = perp.length_sq();
            if d2 <= radius * radius {
                let entry = tc - (radius * radius - d2).max(0.0).sqrt();
                if entry >= 0.0 {
                    t0 = Some(entry);
                }
            }
        }
    }
    let t1 = ray_vs_sphere(origin, dir, a, radius, max_dist);
    let t2 = ray_vs_sphere(origin, dir, b, radius, max_dist);
    let mut cands = Vec::new();
    for t in [t0, t1, t2] {
        if let Some(v) = t {
            cands.push(v);
        }
    }
    if cands.is_empty() {
        return None;
    }
    let t = cands.into_iter().fold(f64::INFINITY, f64::min);
    if t <= max_dist {
        Some(t)
    } else {
        None
    }
}

pub fn ray_vs_aabb(origin: Vec3, dir: Vec3, mn: Vec3, mx: Vec3, max_dist: f64) -> Option<(f64, Vec3)> {
    let mut tmin = 0.0f64;
    let mut tmax = max_dist;
    let mut hit_axis = -1i32;
    let coords = [origin.x, origin.y, origin.z];
    let dirs = [dir.x, dir.y, dir.z];
    let mns = [mn.x, mn.y, mn.z];
    let mxs = [mx.x, mx.y, mx.z];
    for i in 0..3 {
        let o = coords[i];
        let d = dirs[i];
        let mn_i = mns[i];
        let mx_i = mxs[i];
        if d.abs() < 1e-12 {
            if o < mn_i || o > mx_i {
                return None;
            }
            continue;
        }
        let inv = 1.0 / d;
        let mut t1 = (mn_i - o) * inv;
        let mut t2 = (mx_i - o) * inv;
        if t1 > t2 {
            std::mem::swap(&mut t1, &mut t2);
        }
        if t1 > tmin {
            tmin = t1;
            hit_axis = i as i32;
        }
        if t2 < tmax {
            tmax = t2;
        }
        if tmin > tmax {
            return None;
        }
    }
    if tmin < 0.0 || tmin > max_dist || hit_axis < 0 {
        return None;
    }
    let normal = match hit_axis {
        0 => {
            if origin.x < (mn.x + mx.x) * 0.5 {
                Vec3::new(-1.0, 0.0, 0.0)
            } else {
                Vec3::new(1.0, 0.0, 0.0)
            }
        }
        1 => {
            if origin.y < (mn.y + mx.y) * 0.5 {
                Vec3::new(0.0, -1.0, 0.0)
            } else {
                Vec3::new(0.0, 1.0, 0.0)
            }
        }
        _ => {
            if origin.z < (mn.z + mx.z) * 0.5 {
                Vec3::new(0.0, 0.0, -1.0)
            } else {
                Vec3::new(0.0, 0.0, 1.0)
            }
        }
    };
    Some((tmin, normal))
}

// --------------------------------------------------------------------- //
// Hitbox 區域（對齊 ballistics.HIT_REGIONS：順序固定）
// --------------------------------------------------------------------- //
#[derive(Clone, Copy)]
pub struct HitRegion {
    pub id: u8, // 0=頭 1=身 2=腿
    pub mult: f64,
    pub radius: f64,
    pub center_y: f64,
    pub half_height: f64,
}

pub const REGIONS: [HitRegion; 3] = [
    HitRegion { id: 0, mult: HEAD_MULT, radius: 0.18, center_y: 1.65, half_height: 0.20 },
    HitRegion { id: 1, mult: BODY_MULT, radius: 0.30, center_y: 1.05, half_height: 0.42 },
    HitRegion { id: 2, mult: LEGS_MULT, radius: 0.16, center_y: 0.32, half_height: 0.28 },
];

pub fn hit_test_entity(origin: Vec3, dir: Vec3, feet: Vec3, max_dist: f64) -> Option<(f64, u8)> {
    let mut best: Option<(f64, u8)> = None;
    for r in REGIONS.iter() {
        let c = feet.add(Vec3::new(0.0, r.center_y, 0.0));
        let a = c.sub(Vec3::new(0.0, r.half_height, 0.0));
        let b = c.add(Vec3::new(0.0, r.half_height, 0.0));
        if let Some(t) = ray_vs_capsule(origin, dir, a, b, r.radius, max_dist) {
            match best {
                Some((bt, _)) if bt <= t => {}
                _ => best = Some((t, r.id)),
            }
        }
    }
    best
}

// --------------------------------------------------------------------- //
// 世界（最小：玩家狀態 + 牆面）
// --------------------------------------------------------------------- //
pub struct Entity {
    pub feet: Vec3,
    pub alive: bool,
    pub health: f64,
}

pub struct Scene {
    pub walls: Vec<Wall>,
    pub players: Vec<Entity>,
}

pub struct ShotResult {
    pub hits: Vec<HitOut>,
    pub wall_hits: i32,
}

#[derive(Clone, Copy)]
pub struct HitOut {
    pub slot: i32,
    pub region: u8,
    pub base: f64,
    pub dealt: f64,
    pub wall_hits: i32,
}

fn nearest_wall(scene: &Scene, origin: Vec3, dir: Vec3, max_dist: f64) -> Option<(f64, Vec3, Wall)> {
    let mut best: Option<(f64, Vec3, Wall)> = None;
    for w in scene.walls.iter() {
        if let Some((t, n)) = ray_vs_aabb(origin, dir, w.mn, w.mx, max_dist) {
            match best {
                Some((bt, _, _)) if bt <= t => {}
                _ => best = Some((t, n, *w)),
            }
        }
    }
    best
}

/// 對齊 ballistics.resolve_hitscan（狀態跨發保留）
pub fn resolve_hitscan(scene: &mut Scene, shooter: usize, origin: Vec3, dir: Vec3,
                       damage: f64, pen_level: i32, max_dist: f64) -> ShotResult {
    let mut hits = Vec::new();
    let mut wall_hits = 0;
    let mut pos = origin;
    let mut dist_so_far = 0.0;
    let mut pen_mult = 1.0;

    for _ in 0..=MAX_PENETRATIONS {
        let remaining = max_dist - dist_so_far;
        let wall_hit = nearest_wall(scene, pos, dir, remaining);
        let wall_dist = wall_hit.map(|(t, _, _)| t);

        // 最近敵人
        let mut ent_hit: Option<(f64, usize, u8)> = None;
        for (slot, p) in scene.players.iter().enumerate() {
            if slot == shooter || !p.alive {
                continue;
            }
            if let Some((t, rid)) = hit_test_entity(pos, dir, p.feet, remaining) {
                match ent_hit {
                    Some((et, _, _)) if et <= t => {}
                    _ => ent_hit = Some((t, slot, rid)),
                }
            }
        }

        if let Some((t, slot, region)) = ent_hit {
            if wall_dist.is_none() || t <= wall_dist.unwrap() {
                let base = damage * pen_mult;
                let final_dmg = base * REGIONS[region as usize].mult;
                let p = &mut scene.players[slot];
                // apply_damage（vuln mult = 1.0）
                let mut dealt = 0.0;
                dealt += final_dmg;
                p.health -= final_dmg;
                if p.health <= 0.0 && p.alive {
                    p.health = 0.0;
                    p.alive = false;
                }
                hits.push(HitOut { slot: slot as i32, region, base, dealt, wall_hits });
                break;
            }
        }

        match wall_hit {
            None => break,
            Some((tdist, _, w)) => {
                if pen_level < material_req(w.material) {
                    break;
                }
                wall_hits += 1;
                pen_mult *= material_keep(w.material);
                dist_so_far += tdist + 0.3;
                pos = pos.add(dir.mul(tdist + 0.3));
                if dist_so_far >= max_dist {
                    break;
                }
            }
        }
    }
    ShotResult { hits, wall_hits }
}
