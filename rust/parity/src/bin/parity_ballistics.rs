//! Ballistics / Hitbox / 穿透 parity：讀場景重跑，位元組級比對。
use std::fs;
use vanta_parity::ballistics::*;

fn read_f64(buf: &[u8], off: &mut usize) -> f64 {
    let v = f64::from_le_bytes(buf[*off..*off + 8].try_into().unwrap());
    *off += 8;
    v
}

fn main() {
    let dir = env!("CARGO_MANIFEST_DIR");
    let scene = fs::read(format!("{dir}/scene_ballistics.bin")).expect("scene_ballistics.bin 不存在");
    let expected = fs::read(format!("{dir}/expected_ballistics.bin")).expect("expected_ballistics.bin 不存在");

    let mut o = 0usize;
    let n_walls = u32::from_le_bytes(scene[o..o + 4].try_into().unwrap()) as usize;
    o += 4;
    let mut walls = Vec::new();
    for _ in 0..n_walls {
        let mn = Vec3::new(read_f64(&scene, &mut o), read_f64(&scene, &mut o), read_f64(&scene, &mut o));
        let mx = Vec3::new(read_f64(&scene, &mut o), read_f64(&scene, &mut o), read_f64(&scene, &mut o));
        let mat = scene[o];
        o += 1;
        walls.push(Wall { mn, mx, material: mat });
    }
    let n_players = u32::from_le_bytes(scene[o..o + 4].try_into().unwrap()) as usize;
    o += 4;
    let mut players = Vec::new();
    for _ in 0..n_players {
        let feet = Vec3::new(read_f64(&scene, &mut o), read_f64(&scene, &mut o), read_f64(&scene, &mut o));
        let alive = scene[o] == 1;
        o += 1;
        let hp = read_f64(&scene, &mut o);
        players.push(Entity { feet, alive, health: hp });
    }
    let n_shots = u32::from_le_bytes(scene[o..o + 4].try_into().unwrap()) as usize;
    o += 4;
    let mut shots = Vec::new();
    for _ in 0..n_shots {
        let wid = scene[o];
        o += 1;
        let origin = Vec3::new(read_f64(&scene, &mut o), read_f64(&scene, &mut o), read_f64(&scene, &mut o));
        let d = Vec3::new(read_f64(&scene, &mut o), read_f64(&scene, &mut o), read_f64(&scene, &mut o));
        shots.push((wid, origin, d));
    }

    // 武器：0=vandal(40,pen2) 1=classic(26,pen0) 2=operator(150,pen2)
    let dmg = [40.0, 26.0, 150.0];
    let pen = [2, 0, 2];

    let mut scene_sim = Scene { walls, players };
    let mut out: Vec<u8> = Vec::new();
    for (wid, origin, d) in shots {
        let res = resolve_hitscan(&mut scene_sim, 0, origin, d, dmg[wid as usize], pen[wid as usize], MAX_DIST);
        out.extend_from_slice(&(res.hits.len() as u32).to_le_bytes());
        for h in res.hits {
            out.extend_from_slice(&h.slot.to_le_bytes());
            out.push(h.region);
            out.extend_from_slice(&h.base.to_le_bytes());
            out.extend_from_slice(&h.dealt.to_le_bytes());
            out.extend_from_slice(&h.wall_hits.to_le_bytes());
        }
    }
    fs::write(format!("{dir}/expected_ballistics_rust.bin"), &out).unwrap();

    if out == expected {
        println!("✅ BALLISTICS PARITY OK — {n_shots} 發（Hitbox/穿透/跨發狀態）Rust 與 Python 位元組級一致");
    } else {
        let first = out.iter().zip(expected.iter()).position(|(a, b)| a != b).unwrap_or(out.len());
        println!("❌ BALLISTICS PARITY FAIL — 第 {first} 位元組分歧");
        std::process::exit(1);
    }
}
