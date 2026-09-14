//! vanta_parity — 核心模組庫（M1 + M2 + M4 + M13）
//! mt19937：與 Python 端 server/core/rng.py 位元級相容的 MT19937
//! recoil / ballistics / protocol / movement：對應 Python 端實作的 Rust 移植
//! weapons：武器資料庫（20 把武器完整數值）
//! status：10 種狀態干擾系統
//! inventory：3-slot 武器槽位與切換

pub mod abilities;
pub mod ballistics;
pub mod collision;
pub mod inventory;
pub mod movement;
pub mod mt19937;
pub mod protocol;
pub mod recoil;
pub mod status;
pub mod weapon_state;
pub mod match_state;
pub mod weapons;
