//! match_state — 回合狀態機與對戰流程
//!
//! 對齊 Python `server/game/match.py`：
//!   * RoundPhase 狀態機（BUY → ACTION → END → FINISHED）
//!   * 半場交換（12 回合後攻守互換）
//!   * 正規賽先拿 13 分；12-12 延長賽先到 14 分、贏 2 分
//!   * 死鬥模式（DM）：無回合、20 殺或時間到
//!   * 回合逐輪記錄（RoundRecord）
//!   * 經濟結算由外部系統依據 loss_streak / round_winner 處理

use std::fmt;

// ------------------------------------------------------------------ //
// 常量
// ------------------------------------------------------------------ //

pub const ROUNDS_PER_HALF: u32 = 12;
pub const ROUNDS_TO_WIN: u32 = 13;
pub const ROUNDS_OVERTIME: u32 = 14;

pub const BUY_TIME_FIRST: f64 = 30.0;
pub const BUY_TIME_NORMAL: f64 = 30.0;
pub const ACTION_TIME: f64 = 100.0;
pub const END_TIME: f64 = 4.0;

pub const TEAM_ATTACKERS: u8 = 0;
pub const TEAM_DEFENDERS: u8 = 1;

pub const DM_KILLS_TO_WIN: u32 = 40;
pub const DM_TIME_LIMIT: f64 = 540.0;
pub const DM_RESPAWN_TIME: f64 = 3.0;

// ------------------------------------------------------------------ //
// RoundPhase
// ------------------------------------------------------------------ //

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RoundPhase {
    Buy,
    Action,
    End,
    Finished,
}

impl RoundPhase {
    /// 對齊 Python `RoundPhase.value` 用於網路封包
    pub fn as_str(&self) -> &'static str {
        match self {
            RoundPhase::Buy => "buy",
            RoundPhase::Action => "action",
            RoundPhase::End => "end",
            RoundPhase::Finished => "finished",
        }
    }
}

impl fmt::Display for RoundPhase {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

// ------------------------------------------------------------------ //
// MatchConfig — 可調比賽參數
// ------------------------------------------------------------------ //

#[derive(Debug, Clone)]
pub struct MatchConfig {
    pub rounds_per_half: u32,
    pub rounds_to_win: u32,
    pub rounds_overtime: u32,
    pub buy_time_first: f64,
    pub buy_time_normal: f64,
    pub action_time: f64,
    pub end_time: f64,
    pub overtime_enabled: bool,
}

impl Default for MatchConfig {
    fn default() -> Self {
        MatchConfig {
            rounds_per_half: ROUNDS_PER_HALF,
            rounds_to_win: ROUNDS_TO_WIN,
            rounds_overtime: ROUNDS_OVERTIME,
            buy_time_first: BUY_TIME_FIRST,
            buy_time_normal: BUY_TIME_NORMAL,
            action_time: ACTION_TIME,
            end_time: END_TIME,
            overtime_enabled: true,
        }
    }
}

// ------------------------------------------------------------------ //
// RoundRecord — 逐輪資料
// ------------------------------------------------------------------ //

#[derive(Debug, Clone)]
pub struct RoundRecord {
    pub number: u32,
    pub winner: Option<u8>,
    pub reason: String,
}

// ------------------------------------------------------------------ //
// MatchMode
// ------------------------------------------------------------------ //

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MatchMode {
    Competitive,
    Deathmatch,
}

// ------------------------------------------------------------------ //
// MatchState — 完整對戰狀態
// ------------------------------------------------------------------ //

#[derive(Debug, Clone)]
pub struct MatchState {
    pub config: MatchConfig,
    pub mode: MatchMode,
    pub phase: RoundPhase,
    pub round: u32,
    pub scores: [u32; 2],
    pub loss_streak: [u32; 2],
    pub phase_timer: f64,
    pub round_records: Vec<RoundRecord>,
    pub round_winner: Option<u8>,
    pub round_reason: String,
    pub event_log: Vec<String>,
    // 死鬥模式
    pub dm_kill_counts: Vec<u32>,
    pub dm_timer: f64,
    pub dm_respawn_timers: Vec<f64>,
}

impl MatchState {
    /// 建立新的 MatchState（competitive 模式）
    pub fn new() -> Self {
        Self::with_config(MatchConfig::default(), MatchMode::Competitive)
    }

    /// 建立帶自訂配置的 MatchState
    pub fn with_config(config: MatchConfig, mode: MatchMode) -> Self {
        MatchState {
            phase: RoundPhase::Buy,
            round: 1,
            scores: [0, 0],
            loss_streak: [0, 0],
            phase_timer: config.buy_time_first,
            round_records: Vec::new(),
            round_winner: None,
            round_reason: String::new(),
            event_log: Vec::new(),
            dm_kill_counts: vec![0; 10],
            dm_timer: DM_TIME_LIMIT,
            dm_respawn_timers: vec![0.0; 10],
            config,
            mode,
        }
    }

    // ------------------------------------------------------------------ //
    // 攻守判定
    // ------------------------------------------------------------------ //

    /// 傳回當前回合的攻方 team id（0 或 1）
    pub fn attackers(&self) -> u8 {
        self.attackers_of(self.round)
    }

    /// 指定回合號的攻方 team id
    pub fn attackers_of(&self, round_number: u32) -> u8 {
        let half_cycles = self.config.rounds_per_half * 2;
        if (round_number - 1) % half_cycles < self.config.rounds_per_half {
            TEAM_ATTACKERS
        } else {
            TEAM_DEFENDERS
        }
    }

    /// 守方 team id
    pub fn defenders(&self) -> u8 {
        1 - self.attackers()
    }

    /// 半場是否已交換（round > rounds_per_half）
    pub fn half_time_done(&self) -> bool {
        self.round > self.config.rounds_per_half
    }

    // ------------------------------------------------------------------ //
    // 主步進
    // ------------------------------------------------------------------ //

    /// 每幀呼叫；由外部處理具體邏輯（Spike、射擊、移動等）
    pub fn step(&mut self, dt: f64) {
        if self.phase == RoundPhase::Finished {
            return;
        }
        if self.mode == MatchMode::Deathmatch {
            self.step_deathmatch(dt);
            return;
        }
        self.phase_timer -= dt;
        match self.phase {
            RoundPhase::Buy => {
                if self.phase_timer <= 0.0 {
                    self.start_action();
                }
            }
            RoundPhase::Action => {
                // 外部檢查回合結束條件後呼叫 end_round
            }
            RoundPhase::End => {
                if self.phase_timer <= 0.0 {
                    self.settle_and_next_round();
                }
            }
            RoundPhase::Finished => {}
        }
    }

    // ------------------------------------------------------------------ //
    // 狀態轉換
    // ------------------------------------------------------------------ //

    /// BUY → ACTION
    pub fn start_action(&mut self) {
        self.phase = RoundPhase::Action;
        self.phase_timer = self.config.action_time;
        self.event_log
            .push(format!("round{} action start (attackers=team{})", self.round, self.attackers()));
    }

    /// 進入 END 階段
    pub fn end_round(&mut self, winner: u8, reason: &str) {
        if self.phase == RoundPhase::Finished {
            return;
        }
        self.phase = RoundPhase::End;
        self.phase_timer = self.config.end_time;
        self.round_winner = Some(winner);
        self.round_reason = reason.to_string();
        self.scores[winner as usize] += 1;
        self.loss_streak[winner as usize] = 0;
        self.loss_streak[(1 - winner) as usize] += 1;
        self.round_records.push(RoundRecord {
            number: self.round,
            winner: Some(winner),
            reason: reason.to_string(),
        });
        self.event_log
            .push(format!("round{} -> team{} wins ({})", self.round, winner, reason));
    }

    /// END → 下一回合 或 FINISHED
    pub fn settle_and_next_round(&mut self) {
        if self.phase != RoundPhase::End {
            return;
        }

        // 獲勝判定
        let win_threshold = if self.overtime_active() {
            self.config.rounds_overtime
        } else {
            self.config.rounds_to_win
        };

        if let Some(winner) = self.round_winner {
            if self.scores[winner as usize] >= win_threshold {
                self.phase = RoundPhase::Finished;
                let ot_tag = if self.overtime_active() { " (OT)" } else { "" };
                self.event_log.push(format!(
                    "MATCH END{}: team{} wins {}-{}",
                    ot_tag,
                    winner,
                    self.scores[winner as usize],
                    self.scores[(1 - winner) as usize]
                ));
                return;
            }
        }

        self.round += 1;
        self.round_winner = None;
        self.round_reason.clear();
        self.phase = RoundPhase::Buy;
        self.phase_timer = if self.round == 1 || self.round == self.config.rounds_per_half + 1 {
            self.config.buy_time_first
        } else {
            self.config.buy_time_normal
        };
    }

    /// 標記回合已結束（外部完成經濟結算後呼叫）
    pub fn mark_finished(&mut self) {
        self.phase = RoundPhase::Finished;
    }

    // ------------------------------------------------------------------ //
    // 延長賽
    // ------------------------------------------------------------------ //

    /// 延長賽是否啟用
    pub fn overtime_enabled(&self) -> bool {
        self.config.overtime_enabled
    }

    /// 目前是否處於延長賽（12-12 觸發）
    pub fn overtime_active(&self) -> bool {
        self.overtime_enabled()
            && self.scores[0] == self.config.rounds_per_half
            && self.scores[1] == self.config.rounds_per_half
    }

    /// 依當前分數計算勝利門檻
    pub fn win_threshold(&self) -> u32 {
        if self.overtime_active() {
            self.config.rounds_overtime
        } else {
            self.config.rounds_to_win
        }
    }

    /// 檢查是否有一隊已達到獲勝門檻
    pub fn has_winner(&self) -> bool {
        self.scores[0] >= self.win_threshold() || self.scores[1] >= self.win_threshold()
    }

    // ------------------------------------------------------------------ //
    // 死鬥模式
    // ------------------------------------------------------------------ //

    fn step_deathmatch(&mut self, dt: f64) {
        self.dm_timer -= dt;
        for timer in self.dm_respawn_timers.iter_mut() {
            if *timer > 0.0 {
                *timer -= dt;
            }
        }
        for (i, &kills) in self.dm_kill_counts.iter().enumerate() {
            if kills >= DM_KILLS_TO_WIN {
                self.phase = RoundPhase::Finished;
                self.round_reason = format!("player{} reached {} kills", i, DM_KILLS_TO_WIN);
                self.event_log.push(self.round_reason.clone());
                return;
            }
        }
        if self.dm_timer <= 0.0 {
            let winner = self
                .dm_kill_counts
                .iter()
                .enumerate()
                .max_by_key(|(_, &k)| k)
                .map(|(i, _)| i)
                .unwrap_or(0);
            self.phase = RoundPhase::Finished;
            self.round_reason = format!(
                "time up, player{} wins with {} kills",
                winner, self.dm_kill_counts[winner]
            );
            self.event_log.push(self.round_reason.clone());
        }
    }

    /// 記錄擊殺（死鬥模式）
    pub fn dm_record_kill(&mut self, slot: usize) {
        if self.mode == MatchMode::Deathmatch && slot < self.dm_kill_counts.len() {
            self.dm_kill_counts[slot] += 1;
        }
    }

    /// 死鬥復活倒數（死亡時呼叫）
    pub fn dm_start_respawn(&mut self, slot: usize) {
        if self.mode == MatchMode::Deathmatch && slot < self.dm_respawn_timers.len() {
            self.dm_respawn_timers[slot] = DM_RESPAWN_TIME;
        }
    }

    /// 死鬥復活是否就緒
    pub fn dm_can_respawn(&self, slot: usize) -> bool {
        self.mode == MatchMode::Deathmatch
            && slot < self.dm_respawn_timers.len()
            && self.dm_respawn_timers[slot] <= 0.0
    }

    // ------------------------------------------------------------------ //
    // 計分板
    // ------------------------------------------------------------------ //

    pub fn scoreboard(&self) -> Scoreboard {
        Scoreboard {
            round: self.round,
            phase: self.phase,
            scores: self.scores,
            overtime: self.overtime_active(),
            records: self.round_records.clone(),
        }
    }
}

// ------------------------------------------------------------------ //
// Scoreboard — 供序列化
// ------------------------------------------------------------------ //

#[derive(Debug, Clone)]
pub struct Scoreboard {
    pub round: u32,
    pub phase: RoundPhase,
    pub scores: [u32; 2],
    pub overtime: bool,
    pub records: Vec<RoundRecord>,
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_round_flow() {
        let mut m = MatchState::new();
        assert_eq!(m.phase, RoundPhase::Buy);
        assert_eq!(m.round, 1);
        assert_eq!(m.scores, [0, 0]);

        // 時間流逝 → 進入 ACTION
        m.step(31.0);
        assert_eq!(m.phase, RoundPhase::Action);

        // 攻方贏一回合
        m.end_round(0, "attackers_eliminated");
        assert_eq!(m.phase, RoundPhase::End);
        assert_eq!(m.scores, [1, 0]);

        // END 結算
        m.settle_and_next_round();
        assert_eq!(m.phase, RoundPhase::Buy);
        assert_eq!(m.round, 2);
    }

    #[test]
    fn half_time_swap() {
        let mut m = MatchState::new();
        // 第 12 回合結束前，半場交換尚未完成
        m.round = 12;
        assert!(!m.half_time_done());
        // 第 13 回合（半場交換後）
        m.round = 13;
        assert!(m.half_time_done());
        // 13 回合起攻方為 team1
        assert_eq!(m.attackers_of(13), TEAM_DEFENDERS);
    }

    #[test]
    fn overtime_triggers_at_12_12() {
        let mut m = MatchState::new();
        m.scores = [12, 12];
        m.round = 25;
        assert!(m.overtime_active());
        assert_eq!(m.win_threshold(), ROUNDS_OVERTIME);
    }

    #[test]
    fn normal_win_at_13() {
        let mut m = MatchState::new();
        m.scores = [12, 11];
        m.round = 24;
        assert!(!m.overtime_active());
        assert_eq!(m.win_threshold(), ROUNDS_TO_WIN);
    }

    #[test]
    fn deathmatch_finishes_on_kills() {
        let mut m = MatchState::with_config(MatchConfig::default(), MatchMode::Deathmatch);
        m.dm_kill_counts[3] = DM_KILLS_TO_WIN;
        m.step(1.0);
        assert_eq!(m.phase, RoundPhase::Finished);
        assert!(m.round_reason.contains("player3"));
    }

    #[test]
    fn deathmatch_finishes_on_time() {
        let mut m = MatchState::with_config(MatchConfig::default(), MatchMode::Deathmatch);
        m.dm_kill_counts[0] = 5;
        m.dm_kill_counts[1] = 8;
        m.dm_timer = 0.1;
        m.step(1.0);
        assert_eq!(m.phase, RoundPhase::Finished);
        assert!(m.round_reason.contains("player1"));
    }

    #[test]
    fn match_config_custom() {
        let cfg = MatchConfig {
            rounds_to_win: 7,
            action_time: 60.0,
            ..Default::default()
        };
        let m = MatchState::with_config(cfg.clone(), MatchMode::Competitive);
        assert_eq!(m.config.rounds_to_win, 7);
        assert_eq!(m.config.action_time, 60.0);
    }

    #[test]
    fn overtime_disabled() {
        let cfg = MatchConfig {
            overtime_enabled: false,
            ..Default::default()
        };
        let mut m = MatchState::with_config(cfg, MatchMode::Competitive);
        m.scores = [12, 12];
        assert!(!m.overtime_active());
        assert_eq!(m.win_threshold(), ROUNDS_TO_WIN);
    }
}
