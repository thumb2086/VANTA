//! vanta_server — 純 Rust 權威伺服器（M6：完整對戰閉環）
//!
//! 已含（全 Rust、伺服器權威、二進位協定與 Python 位元組一致）：
//!   * 移動/碰撞（空間雜湊）/後座力/換彈/射擊（Rust 彈道 Hitbox+穿透）
//!   * **回合狀態機**（BUY → ACTION → END → 下一回合，半場攻守）
//!   * **經濟系統**（擊殺 +200 / 回合勝 +3000 / 連敗補償 1900→2400→2900 / 安放 +300 / 上限 9000）
//!   * **Spike**（安放 4s / 倒數 45s / 拆除 7s 含 3.5s 檢查點 / 爆炸範圍致死）
//!   * **購買**（步槍/重甲，ACTION_BUY）
//!   * **MATCH_STATE 封包**（phase/round/timer/spike/score/credits）
//!   * **多場併發**（--matches N：每場獨立 socket+狀態，0 cross-talk）
//!
//! 誠實範圍：技能（Ability）僅保留行動解析骨架（充能/冷卻未接效果）；
//! tokio async 為 M6b 升級選項（目前用 std threads 達成多場併發）。
//!
//! 用法：
//!   cargo run --release -- --port 7777 --seconds 0        # 單場（實時）
//!   cargo run --release -- --port 7777 --matches 16      # 16 場併發
//!   cargo run --release -- --port 0 --bench-ticks 76800  # 基準
//!   cargo run --release -- --selftest                    # 內建自測

use std::collections::HashMap;
use std::env;
use std::net::{SocketAddr, UdpSocket};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use vanta_parity::ballistics::{self, Vec3};
use vanta_parity::collision::{SpatialHash, Wall};
use vanta_parity::movement::MovementController;
use vanta_parity::protocol::{
    ActionPkt, InputPkt, MatchStatePkt, SnapshotEntry, SnapshotPkt, WelcomePkt, ACTION_BUY,
    ACTION_DEFUSE, ACTION_PLANT, ACTION_RELOAD, ACTION_SHOOT, TYPE_ACTION,
};
use vanta_parity::recoil::RecoilController;

const DT: f64 = 1.0 / 128.0;
const MAX_SLOTS: usize = 10;
const MAGIC: u8 = 0x56;

// 回合時長（秒；誠實：為 demo 縮短，正式可調）
const BUY_TIME: f64 = 15.0;
const BUY_TIME_FAST: f64 = 1.0;
const ACTION_TIME: f64 = 100.0;
const END_TIME: f64 = 5.0;

// 經濟
const CREDITS_MAX: u16 = 9000;
const CREDITS_START: u16 = 800;
const KILL_REWARD: u16 = 200;
const ROUND_WIN_REWARD: u16 = 3000;
const SPIKE_PLANT_REWARD: u16 = 300;
const LOSS_BONUS: [u16; 3] = [1900, 2400, 2900];

// Spike
const PLANT_TIME: f64 = 4.0;
const FUSE_TIME: f64 = 45.0;
const DEFUSE_TIME: f64 = 7.0;
const DEFUSE_CHECKPOINT: f64 = 3.5;
const EXPLOSION_RADIUS: f64 = 25.0;
const EXPLOSION_DAMAGE: f64 = 150.0;
const SITE_CENTER: (f64, f64) = (0.0, 10.0);   // Spike 點位 A（簡化單點）

// 階段 / Spike 狀態（對齊 Python protocol 常數）
const PHASE_BUY: u8 = 0;
const PHASE_ACTION: u8 = 1;
const PHASE_END: u8 = 2;
const PHASE_FINISHED: u8 = 3;
const SPIKE_IDLE: u8 = 0;
const SPIKE_PLANTING: u8 = 1;
const SPIKE_PLANTED: u8 = 2;
const SPIKE_DEFUSING: u8 = 3;
const SPIKE_DETONATED: u8 = 4;
const SPIKE_DEFUSED: u8 = 5;

// --------------------------------------------------------------------- //
// Player
// --------------------------------------------------------------------- //
struct Player {
    ctrl: MovementController,
    health: f64,
    alive: bool,
    mag: u32,
    reserve: u32,
    reloading: bool,
    reload_progress: f64,
    recoil: RecoilController,
    reload_time: f64,
    mag_size: u32,
    weapon_slot: u8,
    last_input_seq: u32,
    echo_client_time_ms: u32,
    damage: f64,
    pen_level: i32,
    fire_rate_rps: f64,
    next_fire_time: f64,
    aim_yaw_deg: f64,
    aim_pitch_deg: f64,
    kills: u32,
    respawn_at: f64,
    want_fire: bool,
    pending_input: Option<InputPkt>,
    credits: u16,
    team: u8,               // 0=攻 1=守
    shield_hp: f64,
    plant_hold: bool,
    defuse_hold: bool,
}

impl Player {
    fn new(team: u8) -> Self {
        Player {
            ctrl: MovementController::new(Default::default(), 0.0),
            health: 100.0,
            alive: false,           // 無 session = 不參與（避免幽靈擋彈道）
            mag: 12,
            reserve: 60,
            reloading: false,
            reload_progress: 0.0,
            recoil: RecoilController::new(&vanta_parity::recoil::VANDAL, 42),
            reload_time: 1.5,
            mag_size: 12,
            weapon_slot: 1,
            last_input_seq: 0,
            echo_client_time_ms: 0,
            damage: 40.0,
            pen_level: 2,
            fire_rate_rps: 9.75,
            next_fire_time: 0.0,
            aim_yaw_deg: 0.0,
            aim_pitch_deg: 0.0,
            kills: 0,
            respawn_at: 0.0,
            want_fire: false,
            pending_input: None,
            credits: CREDITS_START,
            team,
            shield_hp: 0.0,
            plant_hold: false,
            defuse_hold: false,
        }
    }

    fn apply_damage(&mut self, amount: f64) -> bool {
        self.health -= amount;
        if self.health <= 0.0 && self.alive {
            self.health = 0.0;
            self.alive = false;
            return true;
        }
        false
    }

    fn weapon_update(&mut self, now: f64, dt: f64) {
        self.recoil.update(now, dt);
        if self.reloading {
            self.reload_progress += dt;
            if self.reload_progress >= self.reload_time {
                let need = self.mag_size - self.mag;
                let take = need.min(self.reserve);
                self.mag += take;
                self.reserve -= take;
                self.reloading = false;
                self.reload_progress = 0.0;
            }
        }
    }

    fn reload_progress_byte(&self) -> u8 {
        if !self.reloading {
            255
        } else {
            let frac = (self.reload_progress / self.reload_time.max(1e-9)).min(1.0);
            (frac * 254.0).max(0.0).min(254.0) as u8
        }
    }

    fn buy_item(&mut self, item: i16) -> bool {
        match item {
            0 => self.buy_weapon(2900, 40.0, 2, 9.75, 25, 60, 1.0),   // vandal
            1 => self.buy_weapon(2900, 39.0, 2, 11.0, 30, 90, 1.0),   // phantom
            2 => {
                if self.credits >= 1000 {
                    self.credits -= 1000;
                    self.shield_hp = 50.0;
                    true
                } else {
                    false
                }
            }
            _ => false,
        }
    }

    fn buy_weapon(&mut self, price: u16, dmg: f64, pen: i32, rps: f64,
                  mag: u32, reserve: u32, move_speed: f64) -> bool {
        if self.credits < price {
            return false;
        }
        self.credits -= price;
        self.damage = dmg;
        self.pen_level = pen;
        self.fire_rate_rps = rps;
        self.mag_size = mag;
        self.mag = mag;
        self.reserve = reserve;
        self.reloading = false;
        self.reload_time = 2.5;
        self.weapon_slot = 0;
        self.recoil = RecoilController::new(&vanta_parity::recoil::VANDAL, 42);
        let _ = move_speed;
        true
    }

    fn grant(&mut self, amount: u16) {
        self.credits = (self.credits as u32 + amount as u32).min(CREDITS_MAX as u32) as u16;
    }

    fn spawn_pos(slot: usize) -> Vec3 {
        // 攻方（team0）重生 (x,0,-12)；守方（team1）(x,0,12)
        let xs = [-4.0, -2.0, 0.0, 2.0, 4.0];
        let x = xs[slot % 5];
        if slot < 5 {
            Vec3::new(x, 0.0, -12.0)
        } else {
            Vec3::new(x, 0.0, 12.0)
        }
    }
}

// --------------------------------------------------------------------- //
// Match（回合狀態機 + 經濟 + Spike）
// --------------------------------------------------------------------- //
struct MatchState {
    phase: u8,
    round: u32,
    phase_timer: f64,
    scores: [u8; 2],
    loss_streak: [u32; 2],
    spike_state: u8,
    spike_plant_progress: f64,
    spike_defuse_progress: f64,
    spike_fuse: f64,
    planter: Option<usize>,
    defuser: Option<usize>,
    attacker_team: u8,
    round_winner: Option<u8>,
    winner_slots: Vec<usize>,       // 供 END 結算（勝隊槽位快照）
}

impl MatchState {
    fn new() -> Self {
        MatchState {
            phase: PHASE_BUY,
            round: 1,
            phase_timer: BUY_TIME,
            scores: [0, 0],
            loss_streak: [0, 0],
            spike_state: SPIKE_IDLE,
            spike_plant_progress: 0.0,
            spike_defuse_progress: 0.0,
            spike_fuse: FUSE_TIME,
            planter: None,
            defuser: None,
            attacker_team: 0,
            round_winner: None,
            winner_slots: Vec::new(),
        }
    }

    fn attackers(&self) -> u8 {
        // 半場攻守：前 12 回合攻方 team0，13 起 team1
        if (self.round - 1) % 24 < 12 { 0 } else { 1 }
    }

    fn end_round(&mut self, winner: u8) {
        if self.phase == PHASE_FINISHED {
            return;
        }
        self.phase = PHASE_END;
        self.phase_timer = END_TIME;
        self.round_winner = Some(winner);
        self.scores[winner as usize] = (self.scores[winner as usize] + 1).min(255);
        self.loss_streak[winner as usize] = 0;
        self.loss_streak[(1 - winner) as usize] += 1;
    }
}

// --------------------------------------------------------------------- //
// Server
// --------------------------------------------------------------------- //
struct Server {
    socket: UdpSocket,
    players: Vec<Player>,
    addr_to_slot: HashMap<SocketAddr, usize>,
    free_slots: Vec<usize>,
    hash: SpatialHash,
    sim_walls: Vec<ballistics::Wall>,
    tick: u64,
    time: f64,
    next_net_id: u16,
    match_: MatchState,
    fast: bool,
    matches_total: u32,
}

impl Server {
    fn new(port: u16, walls: Vec<ballistics::Wall>, fast: bool) -> std::io::Result<Self> {
        let socket = UdpSocket::bind(("127.0.0.1", port))?;
        socket.set_nonblocking(true)?;
        let col_walls: Vec<Wall> = walls.iter().map(|w| Wall { mn: w.mn, mx: w.mx }).collect();
        let hash = SpatialHash::new(col_walls);
        let mut server = Server {
            socket,
            players: (0..MAX_SLOTS).map(|i| Player::new(if i < 5 { 0 } else { 1 })).collect(),
            addr_to_slot: HashMap::new(),
            free_slots: (0..MAX_SLOTS).collect(),
            hash,
            sim_walls: walls,
            tick: 0,
            time: 0.0,
            next_net_id: 1,
            match_: MatchState::new(),
            fast,
            matches_total: 1,
        };
        if fast {
            server.match_.phase_timer = BUY_TIME_FAST;
        }
        Ok(server)
    }

    // ------------------------------------------------------------------ #
    fn recv_inputs(&mut self) {
        let mut buf = [0u8; 1024];
        loop {
            match self.socket.recv_from(&mut buf) {
                Ok((n, addr)) => {
                    let data = &buf[..n];
                    if data.len() < 2 || data[0] != MAGIC {
                        continue;
                    }
                    if data[1] == 0x01 {
                        if let Some(pkt) = InputPkt::decode(data) {
                            self.on_input(addr, pkt);
                        }
                    } else if data[1] == TYPE_ACTION {
                        if let Some(pkt) = ActionPkt::decode(data) {
                            self.on_action(addr, pkt);
                        }
                    }
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => break,
                Err(_) => break,
            }
        }
    }

    fn on_input(&mut self, addr: SocketAddr, pkt: InputPkt) {
        let slot = match self.addr_to_slot.get(&addr) {
            Some(&s) => s,
            None => {
                if self.free_slots.is_empty() {
                    return;
                }
                let s = self.free_slots.remove(0);
                self.addr_to_slot.insert(addr, s);
                self.players[s].alive = true;
                self.players[s].health = 100.0;
                self.players[s].pos_reset_round(s);
                let welcome = WelcomePkt { net_id: self.next_net_id, slot: s as u8 }.encode();
                self.next_net_id += 1;
                let _ = self.socket.send_to(&welcome, addr);
                s
            }
        };
        let p = &mut self.players[slot];
        if pkt.input_seq >= p.last_input_seq {
            p.pending_input = Some(pkt);
        }
    }

    fn on_action(&mut self, addr: SocketAddr, pkt: ActionPkt) {
        let slot = match self.addr_to_slot.get(&addr) {
            Some(&s) => s,
            None => return,
        };
        let p = &mut self.players[slot];
        if !p.alive {
            return;
        }
        match pkt.action_id {
            ACTION_SHOOT => {
                p.aim_yaw_deg = pkt.p0 as f64 / 100.0;
                p.aim_pitch_deg = pkt.p1 as f64 / 100.0;
                p.want_fire = true;
            }
            ACTION_RELOAD => {
                if !p.reloading && p.mag < p.mag_size && p.reserve > 0 {
                    p.reloading = true;
                    p.reload_progress = 0.0;
                }
            }
            ACTION_BUY => {
                if self.match_.phase == PHASE_BUY {
                    p.buy_item(pkt.p0);
                }
            }
            ACTION_PLANT => {
                p.plant_hold = pkt.p0 != 0;
            }
            ACTION_DEFUSE => {
                p.defuse_hold = pkt.p0 != 0;
            }
            _ => {}
        }
    }

    // ------------------------------------------------------------------ #
    fn consume_inputs(&mut self) {
        for p in self.players.iter_mut() {
            if !p.alive {
                continue;
            }
            if let Some(inp) = p.pending_input.take() {
                p.last_input_seq = inp.input_seq;
                p.echo_client_time_ms = inp.client_time_ms;
                // BUY/END 階段凍結移動（空氣牆語意：原地煞車）
                if self.match_.phase == PHASE_ACTION {
                    p.ctrl.step(inp.forward, inp.strafe, inp.walk, inp.crouch,
                                inp.jump, DT, 1.0);
                } else {
                    p.ctrl.step(0.0, 0.0, false, false, false, DT, 1.0);
                }
            }
        }
    }

    fn resolve_shots(&mut self) {
        if self.match_.phase != PHASE_ACTION {
            return;
        }
        let ents: Vec<ballistics::Entity> = self
            .players
            .iter()
            .map(|p| ballistics::Entity { feet: p.ctrl.pos, alive: p.alive, health: p.health })
            .collect();
        let walls: Vec<ballistics::Wall> = self.sim_walls.clone();
        let mut scene = ballistics::Scene { walls, players: ents };
        let alive_before: Vec<bool> = scene.players.iter().map(|p| p.alive).collect();
        for i in 0..self.players.len() {
            let (fire, mag_ok, want) = {
                let p = &self.players[i];
                (self.time >= p.next_fire_time, p.mag > 0, p.want_fire)
            };
            if !fire || !mag_ok || !want || !self.players[i].alive {
                continue;
            }
            self.players[i].want_fire = false;
            {
                let p = &mut self.players[i];
                let (po, yo) = p.recoil.fire(self.time);
                p.aim_pitch_deg += po;
                p.aim_yaw_deg += yo;
                p.mag -= 1;
                p.next_fire_time = self.time + 1.0 / p.fire_rate_rps;
            }
            let (yaw, pitch) = {
                let p = &self.players[i];
                (p.aim_yaw_deg.to_radians(), p.aim_pitch_deg.to_radians())
            };
            let dir = Vec3::new(yaw.sin() * pitch.cos(), pitch.sin(), yaw.cos() * pitch.cos());
            let origin = self.players[i].ctrl.pos.add(Vec3::new(0.0, 1.6, 0.0));
            let (damage, pen) = { let p = &self.players[i]; (p.damage, p.pen_level) };
            let res = ballistics::resolve_hitscan(&mut scene, i, origin, dir, damage, pen, 150.0);
            for h in res.hits {
                // ballistics 內建已扣血/死亡（M2 parity）；這裡只判「本發致死」統計
                let target = h.slot as usize;
                if alive_before[target] && !scene.players[target].alive {
                    self.players[i].kills += 1;
                    self.players[i].grant(KILL_REWARD);
                    self.players[target].respawn_at = self.time + 3.0;
                }
            }
        }
        for (i, p) in self.players.iter_mut().enumerate() {
            p.health = scene.players[i].health;
            p.alive = scene.players[i].alive;
        }
    }

    // ------------------------------------------------------------------ #
    // 回合狀態機 + Spike + 經濟
    // ------------------------------------------------------------------ #
    fn match_update(&mut self, dt: f64) {
        let m = &mut self.match_;
        m.phase_timer -= dt;

        match m.phase {
            PHASE_BUY => {
                if m.phase_timer <= 0.0 {
                    m.phase = PHASE_ACTION;
                    m.phase_timer = ACTION_TIME;
                    m.spike_state = SPIKE_IDLE;
                    m.spike_plant_progress = 0.0;
                    m.spike_defuse_progress = 0.0;
                    m.spike_fuse = FUSE_TIME;
                    m.planter = None;
                    m.defuser = None;
                }
            }
            PHASE_ACTION => {
                // Spike：IDLE → 啟動安放（攻方持 hold 且進點）
                if m.spike_state == SPIKE_IDLE {
                    let atk = m.attackers();
                    for (i, p) in self.players.iter().enumerate() {
                        if p.alive && p.team == atk && p.plant_hold {
                            let d = (p.ctrl.pos.x - SITE_CENTER.0).hypot(p.ctrl.pos.z - SITE_CENTER.1);
                            if d <= 2.5 {
                                m.spike_state = SPIKE_PLANTING;
                                m.planter = Some(i);
                                m.spike_plant_progress = 0.0;
                                break;
                            }
                        }
                    }
                }
                // Spike 進度
                if m.spike_state == SPIKE_PLANTING {
                    let planter_ok = m.planter.map_or(false, |s| {
                        let p = &self.players[s];
                        p.alive && p.plant_hold
                            && p.ctrl.vel.horizontal().length() < 0.2
                            && (p.ctrl.pos.x - SITE_CENTER.0).abs() < 2.5
                            && (p.ctrl.pos.z - SITE_CENTER.1).abs() < 2.5
                    });
                    if !planter_ok {
                        m.spike_state = SPIKE_IDLE;
                        m.spike_plant_progress = 0.0;
                        m.planter = None;
                    } else {
                        m.spike_plant_progress += dt;
                        if m.spike_plant_progress >= PLANT_TIME {
                            m.spike_state = SPIKE_PLANTED;
                            m.spike_fuse = FUSE_TIME;
                            // 安放成功：攻方全員 +300
                            let atk = m.attackers();
                            for p in self.players.iter_mut() {
                                if p.team == atk && p.alive {
                                    p.grant(SPIKE_PLANT_REWARD);
                                }
                            }
                        }
                    }
                } else if m.spike_state == SPIKE_PLANTED {
                    m.spike_fuse -= dt;
                    if m.spike_fuse <= 0.0 {
                        m.spike_state = SPIKE_DETONATED;
                        // 爆炸：範圍致死（攻方除外）
                        for p in self.players.iter_mut() {
                            if p.alive && p.team != m.attackers() {
                                let d = (p.ctrl.pos.x - SITE_CENTER.0).hypot(p.ctrl.pos.z - SITE_CENTER.1);
                                if d <= EXPLOSION_RADIUS {
                                    p.apply_damage(EXPLOSION_DAMAGE);
                                }
                            }
                        }
                        let w = m.attackers();
                        m.end_round(w);
                        return;
                    }
                    // 拆除啟動（守方靠近 + defuse_hold）
                    if m.defuser.is_none() {
                        for (i, p) in self.players.iter().enumerate() {
                            if p.alive && p.team != m.attackers() && p.defuse_hold {
                                let d = (p.ctrl.pos.x - SITE_CENTER.0).hypot(p.ctrl.pos.z - SITE_CENTER.1);
                                if d <= 2.0 {
                                    m.defuser = Some(i);
                                    m.spike_state = SPIKE_DEFUSING;
                                    break;
                                }
                            }
                        }
                    }
                } else if m.spike_state == SPIKE_DEFUSING {
                    let ok = m.defuser.map_or(false, |s| {
                        let p = &self.players[s];
                        p.alive && p.defuse_hold
                            && (p.ctrl.pos.x - SITE_CENTER.0).hypot(p.ctrl.pos.z - SITE_CENTER.1) <= 2.0
                    });
                    if !ok {
                        // 中斷：過半保留進度（檢查點）
                        if m.spike_defuse_progress < DEFUSE_CHECKPOINT {
                            m.spike_defuse_progress = 0.0;
                        }
                        m.spike_state = SPIKE_PLANTED;
                        m.defuser = None;
                    } else {
                        m.spike_defuse_progress += dt;
                        if m.spike_defuse_progress >= DEFUSE_TIME {
                            m.spike_state = SPIKE_DEFUSED;
                            let w = 1 - m.attackers();
                            m.end_round(w);
                            return;
                        }
                    }
                }

                // 全滅判定
                let atk = m.attackers();
                let (alive_atk, alive_def) = {
                    let mut a = 0;
                    let mut d = 0;
                    for p in self.players.iter() {
                        if p.alive {
                            if p.team == atk { a += 1 } else { d += 1 }
                        }
                    }
                    (a, d)
                };
                if alive_atk == 0 {
                    let w = 1 - atk;
                    m.end_round(w);
                    return;
                }
                if alive_def == 0 {
                    m.end_round(atk);
                    return;
                }
                // 時間到
                if m.phase_timer <= 0.0 {
                    if m.spike_state != SPIKE_PLANTED && m.spike_state != SPIKE_DEFUSING {
                        let w = 1 - atk;
                        m.end_round(w);
                    } else {
                        m.phase_timer = 0.0;   // 等 Spike 結果
                    }
                }
            }
            PHASE_END => {
                if m.phase_timer <= 0.0 {
                    // 經濟結算
                    if let Some(winner) = m.round_winner {
                        for p in self.players.iter_mut() {
                            if p.team == winner {
                                p.grant(ROUND_WIN_REWARD);
                            } else {
                                let streak = m.loss_streak[p.team as usize];
                                let bonus = LOSS_BONUS[streak.saturating_sub(1).min(2) as usize];
                                p.grant(bonus);
                            }
                        }
                    }
                    // 下一回合
                    m.round += 1;
                    m.round_winner = None;
                    m.phase = PHASE_BUY;
                    m.phase_timer = if self.fast { BUY_TIME_FAST } else { BUY_TIME };
                    m.attacker_team = m.attackers();
                    m.spike_state = SPIKE_IDLE;
                    m.spike_plant_progress = 0.0;
                    m.spike_defuse_progress = 0.0;
                    m.spike_fuse = FUSE_TIME;
                    m.planter = None;
                    m.defuser = None;
                    // 回合重置：重生、血量、彈匣
                    for (i, p) in self.players.iter_mut().enumerate() {
                        p.alive = true;
                        p.health = 100.0;
                        p.shield_hp = p.shield_hp;   // 保留護甲（與特戰一致）
                        p.mag = p.mag_size;
                        p.reserve = p.reserve;
                        p.reloading = false;
                        p.plant_hold = false;
                        p.defuse_hold = false;
                        p.pos_reset_round(i);
                    }
                }
            }
            _ => {}
        }
    }

    fn step(&mut self) {
        self.recv_inputs();
        self.consume_inputs();
        self.resolve_shots();
        for p in self.players.iter_mut() {
            p.weapon_update(self.time, DT);
        }
        // 移動碰撞
        if self.match_.phase == PHASE_ACTION {
            let mut pos: Vec<Vec3> = self.players.iter().map(|p| p.ctrl.pos).collect();
            let mut vel: Vec<Vec3> = self.players.iter().map(|p| p.ctrl.vel).collect();
            let alive: Vec<bool> = self.players.iter().map(|p| p.alive).collect();
            vanta_parity::collision::resolve_world(&mut pos, &mut vel, &alive, &self.hash);
            for (i, p) in self.players.iter_mut().enumerate() {
                p.ctrl.pos = pos[i];
                p.ctrl.vel = vel[i];
            }
        }
        // 回合狀態機（含 Spike/經濟/重生）
        self.match_update(DT);
        // 快照
        let mut entries = Vec::new();
        for (slot, p) in self.players.iter().enumerate() {
            entries.push(SnapshotEntry {
                slot: slot as u8,
                pos: [p.ctrl.pos.x, p.ctrl.pos.y, p.ctrl.pos.z],
                vel: [p.ctrl.vel.x, p.ctrl.vel.y, p.ctrl.vel.z],
                on_ground: p.ctrl.on_ground,
                crouching: p.ctrl.crouching,
                walking: p.ctrl.walking,
                occupied: p.alive || self.addr_to_slot.values().any(|&s| s == slot),
                reloading: p.reloading,
                echo_client_time_ms: p.echo_client_time_ms,
                last_input_seq: p.last_input_seq,
                health: p.health.max(0.0).min(255.0) as u8,
                mag: p.mag.min(255) as u8,
                weapon_slot: p.weapon_slot,
                reload_progress: p.reload_progress_byte(),
            });
        }
        let payload = SnapshotPkt { server_tick: self.tick as u32, entries }.encode();
        let addrs: Vec<SocketAddr> = self.addr_to_slot.keys().cloned().collect();
        for addr in addrs {
            let _ = self.socket.send_to(&payload, addr);
        }
        // MATCH_STATE（每 8 ticks 廣播一次，節省頻寬）
        if self.tick % 8 == 0 {
            let mut credits = [0u16; 10];
            for (i, p) in self.players.iter().enumerate() {
                credits[i] = p.credits;
            }
            let ms = MatchStatePkt {
                server_tick: self.tick as u32,
                phase: self.match_.phase,
                round: self.match_.round.min(255) as u8,
                round_timer_ms: (self.match_.phase_timer.max(0.0) * 1000.0).min(65535.0) as u16,
                spike_state: self.match_.spike_state,
                spike_fuse_s: self.match_.spike_fuse.max(0.0).min(255.0) as u8,
                score_a: self.match_.scores[0],
                score_b: self.match_.scores[1],
                attacker_team: self.match_.attackers(),
                credits,
            };
            let mp = ms.encode();
            let addrs: Vec<SocketAddr> = self.addr_to_slot.keys().cloned().collect();
            for addr in addrs {
                let _ = self.socket.send_to(&mp, addr);
            }
        }
        self.tick += 1;
        self.time = self.tick as f64 * DT;
    }
}

// Player 重生（註冊時與回合重置共用）
impl Player {
    fn pos_reset_round(&mut self, slot: usize) {
        self.ctrl.pos = Player::spawn_pos(slot);
        self.ctrl.vel = Vec3::ZERO;
    }
}

// --------------------------------------------------------------------- //
// 內建 selftest（不經 socket：移動/射擊/回合/經濟/Spike）
// --------------------------------------------------------------------- //
fn selftest() {
    let walls = vec![ballistics::Wall { mn: Vec3::new(-25.0, 0.0, -20.0), mx: Vec3::new(25.0, 12.0, -19.0), material: 3 }];
    let mut server = Server::new(0, walls, false).expect("bind");  // selftest 用標準 BUY 時長
    let a = "127.0.0.1:1".parse::<SocketAddr>().unwrap();
    let b = "127.0.0.1:2".parse::<SocketAddr>().unwrap();
    server.on_input(a, InputPkt { net_id: 1, input_seq: 0, client_time_ms: 1, forward: 0.0, strafe: 0.0, walk: false, crouch: false, jump: false });
    server.on_input(b, InputPkt { net_id: 2, input_seq: 0, client_time_ms: 1, forward: 0.0, strafe: 0.0, walk: false, crouch: false, jump: false });
    let (sa, sb) = (server.addr_to_slot[&a], server.addr_to_slot[&b]);
    // selftest 自訂：A=攻方(team0)、B=守方(team1)（真實伺服器由 slot 決定）
    server.players[sa].team = 0;
    server.players[sb].team = 1;
    assert_eq!(server.players[sa].team, 0);
    assert_eq!(server.players[sb].team, 1);

    // 1) 移動（快進到 ACTION；A 設攻方重生點 -12）
    server.players[sa].ctrl.pos = Vec3::new(0.0, 0.0, -12.0);
    server.match_.phase = PHASE_ACTION;
    for i in 0..128u32 {
        server.on_input(a, InputPkt { net_id: 1, input_seq: 100 + i, client_time_ms: 1, forward: 1.0, strafe: 0.0, walk: false, crouch: false, jump: false });
        server.step();
    }
    let az = server.players[sa].ctrl.pos.z;
    assert!(az > -11.0, "A 未移動: z={az}");
    println!("selftest: 移動 OK (A z={az:.2})");

    // 2) 射擊（近距擊殺 B）
    server.players[sa].ctrl.pos = Vec3::new(0.0, 0.0, 0.0);
    server.players[sa].ctrl.vel = Vec3::ZERO;
    server.players[sb].ctrl.pos = Vec3::new(0.0, 0.0, 3.0);
    server.players[sb].ctrl.vel = Vec3::ZERO;
    server.players[sb].health = 100.0;
    server.players[sb].alive = true;
    server.players[sa].alive = true;
    let mut hit = false;
    for _ in 0..30 {
        server.players[sa].aim_pitch_deg = -server.players[sa].recoil.pitch;
        server.players[sa].aim_yaw_deg = -server.players[sa].recoil.yaw;
        server.on_action(a, ActionPkt { net_id: 1, client_time_ms: 1, input_seq: 999, action_id: ACTION_SHOOT, p0: 0, p1: 0, p2: 0 });
        server.step();
        if server.players[sb].health <= 0.0 { hit = true; break; }
    }
    assert!(hit, "射擊未擊殺");
    let kills = server.players[sa].kills;
    assert!(kills >= 1, "擊殺未計入");
    println!("selftest: 射擊/擊殺 OK (B hp={:.0}, kills={kills})", server.players[sb].health);

    // 3) 經濟：擊殺獎勵 +200
    assert!(server.players[sa].credits >= CREDITS_START + KILL_REWARD, "擊殺經濟錯誤");

    // 4) 安放 Spike → 爆炸 → 攻方勝
    server.players[sa].alive = true;
    server.players[sa].health = 100.0;
    server.players[sa].ctrl.pos = Vec3::new(0.0, 0.0, 10.0);   // 進點
    server.players[sb].alive = true;
    server.players[sb].health = 100.0;
    server.players[sb].ctrl.pos = Vec3::new(0.0, 0.0, 10.0);   // 守方在爆炸範圍
    server.match_.phase = PHASE_ACTION;
    server.match_.spike_state = SPIKE_IDLE;
    server.players[sa].plant_hold = true;
    // 快進安放 4s + 倒數 45s
    for _ in 0..((PLANT_TIME + FUSE_TIME + 1.0) / DT) as usize {
        server.step();
    }
    assert_eq!(server.match_.spike_state, SPIKE_DETONATED, "Spike 未爆炸");
    assert_eq!(server.match_.round_winner, Some(0), "攻方應勝");
    assert!(!server.players[sb].alive, "守方應被炸死");
    println!("selftest: Spike 安放→爆炸 OK（攻方勝，守方陣亡）");

    // 5) 回合結算 → 下一回合 BUY + 經濟
    server.match_.phase = PHASE_END;
    server.match_.phase_timer = 0.01;
    for _ in 0..10 {
        server.step();
    }
    assert_eq!(server.match_.phase, PHASE_BUY, "應回到 BUY");
    assert_eq!(server.match_.round, 2, "應進入第 2 回合");
    // 攻方：800+200(擊殺)+300(安放)+3000(勝) = 4300
    assert_eq!(server.players[sa].credits, 800 + 200 + 300 + 3000, "攻方經濟錯誤");
    // 守方：800 + 連敗補償（連敗 2 次 → 2400）= 3200
    assert_eq!(server.players[sb].credits, 800 + 2400, "守方經濟錯誤");
    println!("selftest: 回合結算/經濟 OK（攻 {}/守 {}）", server.players[sa].credits, server.players[sb].credits);

    // 6) 購買（BUY 階段）
    let before = server.players[sa].credits;
    server.on_action(a, ActionPkt { net_id: 1, client_time_ms: 1, input_seq: 999, action_id: ACTION_BUY, p0: 0, p1: 0, p2: 0 });   // vandal
    assert!(server.players[sa].credits < before, "購買未扣款");
    assert_eq!(server.players[sa].weapon_slot, 0, "購買後應切主武器");
    println!("selftest: 購買 OK（credits {}→{}）", before, server.players[sa].credits);

    // 7) 拆除（守方拆彈）
    server.match_.phase = PHASE_ACTION;
    server.match_.round = 2;
    server.match_.spike_state = SPIKE_PLANTED;
    server.match_.spike_fuse = FUSE_TIME;
    server.players[sa].alive = true;
    server.players[sb].alive = true;
    server.players[sa].health = 100.0;
    server.players[sb].health = 100.0;
    server.players[sb].defuse_hold = true;
    server.players[sb].ctrl.pos = Vec3::new(0.0, 0.0, 10.0);
    for _ in 0..((DEFUSE_TIME + 1.0) / DT) as usize {
        server.step();
    }
    assert_eq!(server.match_.spike_state, SPIKE_DEFUSED, "Spike 未拆除");
    assert_eq!(server.match_.round_winner, Some(1), "守方應勝");
    println!("selftest: 拆除 OK（守方勝）");
    println!("✅ vanta_server selftest 全過（移動/射擊/經濟/Spike/購買/拆除/回合）");
}

// --------------------------------------------------------------------- //
// main
// --------------------------------------------------------------------- //
fn main() {
    let args: Vec<String> = env::args().collect();
    let mut port = 7777u16;
    let mut seconds = 0.0f64;
    let mut bench_ticks = 0u64;
    let mut matches = 1u32;
    let mut fast = false;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--port" => { i += 1; port = args[i].parse().unwrap_or(7777); }
            "--seconds" => { i += 1; seconds = args[i].parse().unwrap_or(0.0); }
            "--bench-ticks" => { i += 1; bench_ticks = args[i].parse().unwrap_or(0); }
            "--matches" => { i += 1; matches = args[i].parse().unwrap_or(1); }
            "--fast" => { fast = true; }
            _ => {}
        }
        i += 1;
    }
    if args.iter().any(|a| a == "--selftest") {
        selftest();
        return;
    }

    let walls = vec![
        ballistics::Wall { mn: Vec3::new(-25.0, 0.0, -20.0), mx: Vec3::new(25.0, 12.0, -19.0), material: 3 },
        ballistics::Wall { mn: Vec3::new(-25.0, 0.0, 20.0), mx: Vec3::new(25.0, 12.0, 21.0), material: 3 },
        ballistics::Wall { mn: Vec3::new(-25.0, 0.0, -20.0), mx: Vec3::new(-24.0, 12.0, 20.0), material: 3 },
        ballistics::Wall { mn: Vec3::new(24.0, 0.0, -20.0), mx: Vec3::new(25.0, 12.0, 20.0), material: 3 },
    ];
    let walls = Arc::new(walls);

    // 多場併發：每場一個 std thread + 獨立 socket/狀態（0 cross-talk）
    if matches > 1 {
        println!("⚔  vanta_server (Rust) — {matches} 場併發（std threads，每場獨立埠 {port}..{}）", port + matches as u16 - 1);
        let mut handles = Vec::new();
        for m in 0..matches {
            let walls = Arc::clone(&walls);
            handles.push(thread::spawn(move || {
                run_one(port + m as u16, (*walls).clone(), seconds, bench_ticks, fast);
            }));
        }
        for h in handles {
            let _ = h.join();
        }
        return;
    }

    run_one(port, (*walls).clone(), seconds, bench_ticks, fast);
}

fn run_one(port: u16, walls: Vec<ballistics::Wall>, seconds: f64, bench_ticks: u64, fast: bool) {
    let mut server = Server::new(port, walls, fast).expect("無法綁定 UDP socket");
    println!("⚔  vanta_server (Rust) @ 127.0.0.1:{port} — 純 Rust 權威伺服器（M6 完整對戰）");

    if bench_ticks > 0 {
        let t0 = Instant::now();
        for _ in 0..bench_ticks {
            server.step();
        }
        let el = t0.elapsed().as_secs_f64();
        println!(
            "[bench] {bench_ticks} ticks 耗時 {el:.3}s → 即時倍率 {:.1}x | 每 tick {:.3} µs",
            bench_ticks as f64 * DT / el,
            el / bench_ticks as f64 * 1e6
        );
        return;
    }

    let mut acc = 0.0f64;
    let mut last = Instant::now();
    let t0 = Instant::now();
    loop {
        let now = Instant::now();
        acc += now.duration_since(last).as_secs_f64();
        last = now;
        while acc >= DT {
            server.step();
            acc -= DT;
        }
        if seconds > 0.0 && t0.elapsed().as_secs_f64() >= seconds {
            break;
        }
        std::thread::sleep(Duration::from_micros(200));
    }
    let el = t0.elapsed().as_secs_f64();
    println!(
        "完成(port {}): {} ticks / {:.2}s → 即時倍率 {:.1}x | 回合={} 比分={}:{}",
        port,
        server.tick,
        el,
        server.tick as f64 * DT / el,
        server.match_.round,
        server.match_.scores[0],
        server.match_.scores[1],
    );
}
