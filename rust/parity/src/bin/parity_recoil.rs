//! Recoil + Seeded RNG parity：重放 Python 黃金軌跡，位元組級比對。
use std::fs;
use vanta_parity::recoil::*;

fn main() {
    let dir = env!("CARGO_MANIFEST_DIR");
    let sched = fs::read(format!("{dir}/schedule_recoil.bin")).expect("schedule_recoil.bin 不存在");
    let expected = fs::read(format!("{dir}/states_recoil.bin")).expect("states_recoil.bin 不存在");
    let t = u32::from_le_bytes(sched[0..4].try_into().unwrap()) as usize;
    assert_eq!(t * 1 + 4, sched.len(), "schedule 大小不符");

    let mut ctrl = RecoilController::new(&VANDAL, 42);
    let mut out: Vec<u8> = Vec::with_capacity(t * 24);
    for i in 0..t {
        let now = i as f64 / 128.0;
        if sched[4 + i] == 1 {
            ctrl.fire(now);
        }
        ctrl.update(now, 1.0 / 128.0);
        out.extend_from_slice(&ctrl.pitch.to_le_bytes());
        out.extend_from_slice(&ctrl.yaw.to_le_bytes());
        out.extend_from_slice(&ctrl.bullet_index.to_le_bytes());
        out.extend_from_slice(&ctrl.shots_fired.to_le_bytes());
    }
    fs::write(format!("{dir}/states_recoil_rust.bin"), &out).unwrap();

    if out == expected {
        println!("✅ RECOIL PARITY OK — {t} ticks（seed=42, vandal 圖案）Rust 與 Python 位元組級一致");
    } else {
        let first = out.iter().zip(expected.iter()).position(|(a, b)| a != b).unwrap_or(out.len());
        println!("❌ RECOIL PARITY FAIL — 第 {first} 位元組分歧");
        std::process::exit(1);
    }
}
