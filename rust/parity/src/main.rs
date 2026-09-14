//! vanta_parity — M1 移動 golden 比對（使用 lib::movement，含 speed_mult=1.0）
use std::env;
use std::fs;

use vanta_parity::movement::MovementController;

fn main() {
    let args: Vec<String> = env::args().collect();
    let base = if args.len() >= 4 {
        args[1..4].to_vec()
    } else {
        let dir = env!("CARGO_MANIFEST_DIR");
        vec![
            format!("{dir}/inputs.bin"),
            format!("{dir}/states.bin"),
            format!("{dir}/states_rust.bin"),
        ]
    };
    let (in_path, exp_path, out_path) = (&base[0], &base[1], &base[2]);

    let inputs = fs::read(in_path).expect("讀取 inputs.bin 失敗（先執行 python3 rust/parity/golden.py）");
    let expected = fs::read(exp_path).expect("讀取 states.bin 失敗");
    let per_tick = 17; // 2×f64 (16B) + flags (u8)
    let n = inputs.len() / per_tick;
    assert_eq!(n * per_tick, inputs.len(), "inputs.bin 大小不符");

    let mut ctrl = MovementController::new(Default::default(), 0.0);
    let mut out: Vec<u8> = Vec::with_capacity(n * 48);

    for i in 0..n {
        let off = i * per_tick;
        let fwd = f64::from_le_bytes(inputs[off..off + 8].try_into().unwrap());
        let str_ = f64::from_le_bytes(inputs[off + 8..off + 16].try_into().unwrap());
        let flags = inputs[off + 16];
        let (walk, crouch, jump, ads) =
            (flags & 1 != 0, flags & 2 != 0, flags & 4 != 0, flags & 8 != 0);
        ctrl.step(fwd, str_, walk, crouch, jump, ads, 1.0 / 128.0, 1.0);
        for v in [ctrl.pos.x, ctrl.pos.y, ctrl.pos.z, ctrl.vel.x, ctrl.vel.y, ctrl.vel.z] {
            out.extend_from_slice(&v.to_le_bytes());
        }
    }

    fs::write(out_path, &out).expect("寫出 states_rust.bin 失敗");

    if out == expected {
        println!("✅ PARITY OK — {n} ticks，Rust 與 Python 位元組級一致（{out_path}）");
    } else {
        let first = out
            .iter()
            .zip(expected.iter())
            .position(|(a, b)| a != b)
            .map(|i| i / 8)
            .unwrap_or(out.len() / 8);
        println!("❌ PARITY FAIL — 第 {first} 個 f64 開始分歧（共 {} f64）", out.len() / 8);
        std::process::exit(1);
    }
}
