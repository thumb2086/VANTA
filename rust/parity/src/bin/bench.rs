//! 效能基準：Rust MovementController 模擬速度（防迴圈優化假象）
use std::env;
use std::fs;

use vanta_parity::movement::MovementController;

fn main() {
    let args: Vec<String> = env::args().collect();
    let path = if args.len() >= 2 { args[1].clone() } else { "inputs.bin".into() };
    let inputs = fs::read(&path).expect("inputs.bin 不存在");
    let n = inputs.len() / 17;
    let mut fwds = Vec::with_capacity(n);
    let mut strs = Vec::with_capacity(n);
    let mut flags = Vec::with_capacity(n);
    for i in 0..n {
        let off = i * 17;
        fwds.push(f64::from_le_bytes(inputs[off..off + 8].try_into().unwrap()));
        strs.push(f64::from_le_bytes(inputs[off + 8..off + 16].try_into().unwrap()));
        flags.push(inputs[off + 16]);
    }
    // 熱身
    let mut c = MovementController::new(Default::default(), 0.0);
    for i in 0..n {
        c.step(fwds[i], strs[i], flags[i] & 1 != 0, flags[i] & 2 != 0, flags[i] & 4 != 0, flags[i] & 8 != 0, 1.0 / 128.0, 1.0);
    }
    // 計時：10 位玩家 × 1000 遍；每遍偏移輸入起點 → 防 LLVM 迴圈優化
    let players = 10;
    let reps = 1000;
    let t0 = std::time::Instant::now();
    let mut acc: f64 = 0.0;
    for r in 0..reps {
        let mut ctrls: Vec<MovementController> = (0..players)
            .map(|_| MovementController::new(Default::default(), 0.0))
            .collect();
        let start = r % n;
        for k in 0..n {
            let i = (start + k) % n;
            for p in 0..players {
                let c = &mut ctrls[p];
                c.step(fwds[i], strs[i], flags[i] & 1 != 0, flags[i] & 2 != 0, flags[i] & 4 != 0, flags[i] & 8 != 0, 1.0 / 128.0, 1.0);
                acc += c.pos.x * 1e-18;
            }
        }
        std::hint::black_box(&ctrls);
    }
    let el = t0.elapsed();
    let total_ticks = (reps * n * players) as f64;
    println!(
        "Rust: {} ticks 耗時 {:.3}s → {:.1} M ticks/s | 每 tick {:.2} ns",
        total_ticks,
        el.as_secs_f64(),
        total_ticks / el.as_secs_f64() / 1e6,
        el.as_secs_f64() / total_ticks * 1e9
    );
    let _ = acc;
}
