//! Protocol — 對齊 server/netcode/protocol.py 的位元布局
//! 以固定偏移讀寫位元組（零分配讀取）；decode → re-encode 必須位元組一致。

pub const MAGIC: u8 = 0x56;
pub const TYPE_INPUT: u8 = 0x01;
pub const TYPE_SNAPSHOT: u8 = 0x02;
pub const TYPE_WELCOME: u8 = 0x03;
pub const TYPE_GAME_EVENT: u8 = 0x05;
pub const TYPE_ACTION: u8 = 0x04;

pub const ACTION_SHOOT: u8 = 0x01;
pub const ACTION_RELOAD: u8 = 0x02;
pub const ACTION_BUY: u8 = 0x03;
pub const ACTION_PLANT: u8 = 0x04;
pub const ACTION_DEFUSE: u8 = 0x05;
pub const ACTION_ABILITY: u8 = 0x06;
pub const ACTION_SWITCH: u8 = 0x07;
pub const TYPE_MATCH_STATE: u8 = 0x06;

pub const MAX_SLOTS: usize = 10;
pub const SNAPSHOT_HEADER: usize = 10;
pub const SNAPSHOT_ENTRY: usize = 26;

const FLAG_WALK: u8 = 0x01;
const FLAG_ADS: u8 = 0x08;
const FLAG_CROUCH: u8 = 0x02;
const FLAG_JUMP: u8 = 0x04;
const FLAG_ON_GROUND: u8 = 0x01;
const FLAG_OCCUPIED: u8 = 0x08;
const FLAG_RELOADING: u8 = 0x10;

const QUANT: f64 = 0.01;

fn clamp_f(v: f64, lo: f64, hi: f64) -> f64 {
    if v < lo {
        lo
    } else if v > hi {
        hi
    } else {
        v
    }
}

// Python round() = 銀行家捨入（ties to even）；Rust f64::round_ties_even 與之相符
fn q16(v: f64) -> i16 {
    (clamp_f(v, -327.67, 327.67) / QUANT).round_ties_even() as i16
}
fn unq16(raw: i16) -> f64 {
    raw as f64 * QUANT
}
fn i8(v: f64) -> i8 {
    (clamp_f(v, -1.0, 1.0) * 127.0).round_ties_even() as i8
}
fn uni8(raw: i8) -> f64 {
    raw as f64 / 127.0
}

// --------------------------------------------------------------------- //
// INPUT（15B）
// --------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct InputPkt {
    pub net_id: u16,
    pub input_seq: u32,
    pub client_time_ms: u32,
    pub forward: f64,
    pub strafe: f64,
    pub walk: bool,
    pub crouch: bool,
    pub jump: bool,
    pub ads: bool,
}

impl InputPkt {
    pub fn encode(&self) -> [u8; 15] {
        let mut d = [0u8; 15];
        d[0] = MAGIC;
        d[1] = TYPE_INPUT;
        d[2..4].copy_from_slice(&self.net_id.to_le_bytes());
        d[4..8].copy_from_slice(&self.input_seq.to_le_bytes());
        d[8..12].copy_from_slice(&self.client_time_ms.to_le_bytes());
        d[12] = i8(self.forward) as u8;
        d[13] = i8(self.strafe) as u8;
        let mut f = 0u8;
        if self.walk {
            f |= FLAG_WALK;
        }
        if self.crouch {
            f |= FLAG_CROUCH;
        }
        if self.jump {
            f |= FLAG_JUMP;
        }
        if self.ads {
            f |= FLAG_ADS;
        }
        d[14] = f;
        d
    }

    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != 15 || d[0] != MAGIC || d[1] != TYPE_INPUT {
            return None;
        }
        Some(InputPkt {
            net_id: u16::from_le_bytes(d[2..4].try_into().ok()?),
            input_seq: u32::from_le_bytes(d[4..8].try_into().ok()?),
            client_time_ms: u32::from_le_bytes(d[8..12].try_into().ok()?),
            forward: uni8(d[12] as i8),
            strafe: uni8(d[13] as i8),
            walk: d[14] & FLAG_WALK != 0,
            crouch: d[14] & FLAG_CROUCH != 0,
            jump: d[14] & FLAG_JUMP != 0,
            ads: d[14] & FLAG_ADS != 0,
        })
    }
}

// --------------------------------------------------------------------- //
// SNAPSHOT（10 + 26×10 = 270B）
// --------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SnapshotEntry {
    pub slot: u8,
    pub pos: [f64; 3],
    pub vel: [f64; 3],
    pub on_ground: bool,
    pub crouching: bool,
    pub walking: bool,
    pub occupied: bool,
    pub reloading: bool,
    pub echo_client_time_ms: u32,
    pub last_input_seq: u32,
    pub health: u8,
    pub mag: u8,
    pub weapon_slot: u8,
    pub reload_progress: u8,
}

impl SnapshotEntry {
    fn flags(&self) -> u8 {
        let mut f = 0u8;
        if self.on_ground {
            f |= FLAG_ON_GROUND;
        }
        if self.crouching {
            f |= FLAG_CROUCH;
        }
        if self.walking {
            f |= FLAG_WALK;
        }
        if self.occupied {
            f |= FLAG_OCCUPIED;
        }
        if self.reloading {
            f |= FLAG_RELOADING;
        }
        f
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct SnapshotPkt {
    pub server_tick: u32,
    pub entries: Vec<SnapshotEntry>,
}

impl SnapshotPkt {
    pub fn encode(&self) -> Vec<u8> {
        let mut d = vec![0u8; SNAPSHOT_HEADER + MAX_SLOTS * SNAPSHOT_ENTRY];
        d[0] = MAGIC;
        d[1] = TYPE_SNAPSHOT;
        d[2..6].copy_from_slice(&self.server_tick.to_le_bytes());
        d[6] = self.entries.len() as u8;
        let mut by_slot = [None; MAX_SLOTS];
        for e in &self.entries {
            by_slot[e.slot as usize] = Some(*e);
        }
        for slot in 0..MAX_SLOTS {
            let off = SNAPSHOT_HEADER + slot * SNAPSHOT_ENTRY;
            match by_slot[slot] {
                None => {
                    // 與 Python 一致：佔用旗標 0、echo/last_seq 0（其餘 bytearray 初始 0）
                    d[off + 1] = 0;
                    d[off + 12..off + 16].copy_from_slice(&0u32.to_le_bytes());
                    d[off + 18..off + 22].copy_from_slice(&0u32.to_le_bytes());
                }
                Some(e) => {
                    d[off] = e.slot;
                    d[off + 1] = e.flags();
                    d[off + 2..off + 4].copy_from_slice(&q16(e.pos[0]).to_le_bytes());
                    d[off + 4..off + 6].copy_from_slice(&q16(e.pos[1]).to_le_bytes());
                    d[off + 6..off + 8].copy_from_slice(&q16(e.pos[2]).to_le_bytes());
                    d[off + 8..off + 10].copy_from_slice(&q16(e.vel[0]).to_le_bytes());
                    d[off + 10..off + 12].copy_from_slice(&q16(e.vel[1]).to_le_bytes());
                    d[off + 12..off + 14].copy_from_slice(&q16(e.vel[2]).to_le_bytes());
                    d[off + 14..off + 18].copy_from_slice(&e.echo_client_time_ms.to_le_bytes());
                    d[off + 18..off + 22].copy_from_slice(&e.last_input_seq.to_le_bytes());
                    d[off + 22] = e.health;
                    d[off + 23] = e.mag;
                    d[off + 24] = e.weapon_slot;
                    d[off + 25] = e.reload_progress;
                }
            }
        }
        d
    }

    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != SNAPSHOT_HEADER + MAX_SLOTS * SNAPSHOT_ENTRY || d[0] != MAGIC || d[1] != TYPE_SNAPSHOT {
            return None;
        }
        let server_tick = u32::from_le_bytes(d[2..6].try_into().ok()?);
        let mut entries = Vec::new();
        for slot in 0..MAX_SLOTS {
            let off = SNAPSHOT_HEADER + slot * SNAPSHOT_ENTRY;
            let flags = d[off + 1];
            let occupied = flags & FLAG_OCCUPIED != 0;
            if !occupied {
                continue;
            }
            let px = unq16(i16::from_le_bytes(d[off + 2..off + 4].try_into().ok()?));
            let py = unq16(i16::from_le_bytes(d[off + 4..off + 6].try_into().ok()?));
            let pz = unq16(i16::from_le_bytes(d[off + 6..off + 8].try_into().ok()?));
            let vx = unq16(i16::from_le_bytes(d[off + 8..off + 10].try_into().ok()?));
            let vy = unq16(i16::from_le_bytes(d[off + 10..off + 12].try_into().ok()?));
            let vz = unq16(i16::from_le_bytes(d[off + 12..off + 14].try_into().ok()?));
            let echo = u32::from_le_bytes(d[off + 14..off + 18].try_into().ok()?);
            let last_seq = u32::from_le_bytes(d[off + 18..off + 22].try_into().ok()?);
            entries.push(SnapshotEntry {
                slot: slot as u8,
                pos: [px, py, pz],
                vel: [vx, vy, vz],
                on_ground: flags & FLAG_ON_GROUND != 0,
                crouching: flags & FLAG_CROUCH != 0,
                walking: flags & FLAG_WALK != 0,
                occupied: true,
                reloading: flags & FLAG_RELOADING != 0,
                echo_client_time_ms: echo,
                last_input_seq: last_seq,
                health: d[off + 22],
                mag: d[off + 23],
                weapon_slot: d[off + 24],
                reload_progress: d[off + 25],
            });
        }
        Some(SnapshotPkt { server_tick, entries })
    }
}

// --------------------------------------------------------------------- //
// ACTION（19B，對齊 server/netcode/protocol.py）
// --------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ActionPkt {
    pub net_id: u16,
    pub client_time_ms: u32,
    pub input_seq: u32,
    pub action_id: u8,
    pub p0: i16,
    pub p1: i16,
    pub p2: i16,
}

impl ActionPkt {
    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != 19 || d[0] != MAGIC || d[1] != TYPE_ACTION {
            return None;
        }
        Some(ActionPkt {
            net_id: u16::from_le_bytes(d[2..4].try_into().ok()?),
            client_time_ms: u32::from_le_bytes(d[4..8].try_into().ok()?),
            input_seq: u32::from_le_bytes(d[8..12].try_into().ok()?),
            action_id: d[12],
            p0: i16::from_le_bytes(d[13..15].try_into().ok()?),
            p1: i16::from_le_bytes(d[15..17].try_into().ok()?),
            p2: i16::from_le_bytes(d[17..19].try_into().ok()?),
        })
    }
}


// --------------------------------------------------------------------- //
// MATCH_STATE（36B，對齊 server/netcode/protocol.py）
// --------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MatchStatePkt {
    pub server_tick: u32,
    pub phase: u8,
    pub round: u8,
    pub round_timer_ms: u16,
    pub spike_state: u8,
    pub spike_fuse_s: u8,
    pub score_a: u8,
    pub score_b: u8,
    pub attacker_team: u8,
    pub credits: [u16; 10],
}

impl MatchStatePkt {
    pub fn encode(&self) -> [u8; 36] {
        let mut d = [0u8; 36];
        d[0] = MAGIC;
        d[1] = TYPE_MATCH_STATE;
        d[2..6].copy_from_slice(&self.server_tick.to_le_bytes());
        d[6] = self.phase;
        d[7] = self.round;
        d[8..10].copy_from_slice(&self.round_timer_ms.to_le_bytes());
        d[10] = self.spike_state;
        d[11] = self.spike_fuse_s;
        d[12] = self.score_a;
        d[13] = self.score_b;
        d[14] = self.attacker_team;
        for i in 0..10 {
            d[16 + i * 2..18 + i * 2].copy_from_slice(&self.credits[i].to_le_bytes());
        }
        d
    }
    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != 36 || d[0] != MAGIC || d[1] != TYPE_MATCH_STATE {
            return None;
        }
        let mut credits = [0u16; 10];
        for i in 0..10 {
            credits[i] = u16::from_le_bytes(d[16 + i * 2..18 + i * 2].try_into().ok()?);
        }
        Some(MatchStatePkt {
            server_tick: u32::from_le_bytes(d[2..6].try_into().ok()?),
            phase: d[6],
            round: d[7],
            round_timer_ms: u16::from_le_bytes(d[8..10].try_into().ok()?),
            spike_state: d[10],
            spike_fuse_s: d[11],
            score_a: d[12],
            score_b: d[13],
            attacker_team: d[14],
            credits,
        })
    }
}

// --------------------------------------------------------------------- //
// WELCOME（6B）
// --------------------------------------------------------------------- //

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WelcomePkt {
    pub net_id: u16,
    pub slot: u8,
}

impl WelcomePkt {
    pub fn encode(&self) -> [u8; 6] {
        let mut d = [0u8; 6];
        d[0] = MAGIC;
        d[1] = TYPE_WELCOME;
        d[2..4].copy_from_slice(&self.net_id.to_le_bytes());
        d[4] = self.slot;
        d
    }
    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != 6 || d[0] != MAGIC || d[1] != TYPE_WELCOME {
            return None;
        }
        Some(WelcomePkt {
            net_id: u16::from_le_bytes(d[2..4].try_into().ok()?),
            slot: d[4],
        })
    }
}

// --------------------------------------------------------------------- //
// GAME_EVENT（16B）
// --------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GameEventPkt {
    pub event: u16,
    pub server_tick: u32,
    pub p0: u32,
    pub p1: u32,
}

impl GameEventPkt {
    pub fn encode(&self) -> [u8; 16] {
        let mut d = [0u8; 16];
        d[0] = MAGIC;
        d[1] = TYPE_GAME_EVENT;
        d[2..4].copy_from_slice(&self.event.to_le_bytes());
        d[4..8].copy_from_slice(&self.server_tick.to_le_bytes());
        d[8..12].copy_from_slice(&self.p0.to_le_bytes());
        d[12..16].copy_from_slice(&self.p1.to_le_bytes());
        d
    }
    pub fn decode(d: &[u8]) -> Option<Self> {
        if d.len() != 16 || d[0] != MAGIC || d[1] != TYPE_GAME_EVENT {
            return None;
        }
        Some(GameEventPkt {
            event: u16::from_le_bytes(d[2..4].try_into().ok()?),
            server_tick: u32::from_le_bytes(d[4..8].try_into().ok()?),
            p0: u32::from_le_bytes(d[8..12].try_into().ok()?),
            p1: u32::from_le_bytes(d[12..16].try_into().ok()?),
        })
    }
}
