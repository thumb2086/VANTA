//! vanta_parity — 核心模組庫（M1 + M2）
//! mt19937：與 Python 端 server/core/rng.py 位元級相容的 MT19937
//! recoil / ballistics / protocol / movement：對應 Python 端實作的 Rust 移植

pub mod ballistics;
pub mod collision;
pub mod movement;
pub mod mt19937;
pub mod protocol;
pub mod recoil;
