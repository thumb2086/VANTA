"""
server/game/match.py — M7 回合狀態機與對戰流程
===============================================
Buy Phase → Action Phase → End Phase，加上：
  * 半場交換（12 回合後攻守互換）
  * 先拿 13 分獲勝
  * 回合結束結算經濟（勝利 3000 / 連敗補償，見 economy.py）
  * 回合重置：重生、血量、彈匣（保留已購武器與護甲）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from server.core.math_core import Vec3
from server.game.economy import ROUND_WIN_REWARD, loss_bonus
from server.game.modes import (
    COMPETITIVE, DEATHMATCH, SPIKERUSH, SWIFTPLAY,
    mode_rules, sp_round_grant, sr_round_weapon, sr_round_shield, OrbField,
)


@dataclass
class PlayerMatchStats:
    player_id: int
    team: int
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    score: int = 0
    damage: int = 0
    first_kills: int = 0
    first_deaths: int = 0
    plants: int = 0
    defuses: int = 0
    economy: int = 0
    alive: bool = True

    def compute_score(self) -> None:
        self.score = int(self.kills * 3.0 + self.assists * 1.0 + self.damage * 0.01)


@dataclass
class MatchResult:
    match_id: str = ""
    winner: int = -1
    scores: dict = field(default_factory=lambda: {0: 0, 1: 0})
    total_rounds: int = 0
    player_stats: dict = field(default_factory=dict)
    round_records: list = field(default_factory=list)
    is_ranked: bool = False
    elo_changes: dict = field(default_factory=dict)

    def get_team_stats(self, team: int) -> list[PlayerMatchStats]:
        return [s for s in self.player_stats.values() if s.team == team]

    def get_winner_ids(self) -> list[int]:
        return [s.player_id for s in self.get_team_stats(self.winner)]

    def get_loser_ids(self) -> list[int]:
        return [s.player_id for s in self.get_team_stats(1 - self.winner)]

ROUNDS_PER_HALF = 12
ROUNDS_TO_WIN = 13
ROUNDS_OVERTIME = 14  # 延長賽：12-12 時先到 14 勝
BUY_TIME_FIRST = 30.0
BUY_TIME_NORMAL = 30.0
ACTION_TIME = 100.0
END_TIME = 4.0

TEAM_ATTACKERS = 0
TEAM_DEFENDERS = 1

# 死鬥模式常量
DM_KILLS_TO_WIN = 40
DM_TIME_LIMIT = 540.0  # 9 分鐘
DM_RESPAWN_TIME = 3.0


class RoundPhase(Enum):
    BUY = "buy"
    ACTION = "action"
    END = "end"
    FINISHED = "finished"


@dataclass(slots=True)
class RoundRecord:
    number: int
    winner: int | None
    reason: str


TDM_KILLS_TO_WIN = 100
TDM_TIME_LIMIT = 300.0
TDM_RESPAWN = 2.0


class Match:
    def __init__(self, world, config=None, mode: str = "competitive"):
        self.world = world
        self.mode = mode  # competitive / deathmatch / spikerush / swiftplay / teamdeathmatch
        self.rules = mode_rules(mode) if mode not in ("deathmatch", "teamdeathmatch") else None
        self.phase = RoundPhase.BUY
        self.round = 1
        self.scores = {0: 0, 1: 0}
        self.loss_streak = {0: 0, 1: 0}
        self.phase_timer = self._buy_time_for_round(1)
        self.round_records: list[RoundRecord] = []
        self.round_winner: int | None = None
        self.round_reason = ""
        self.event_log: list[str] = []
        # Spike Rush 專用：orb 場地＋本回合配裝
        self.orb_field = OrbField()
        self.sr_loadout = ""
        # Swiftplay 專用：上一回合勝隊（經濟配給用）
        self._sp_prev_winner: int | None = None
        # 死鬥 / 團隊死鬥
        self.dm_kill_counts: list[int] = [0] * 10  # 每人擊殺數
        self.tdm_team_kills = [0, 0]
        self.dm_timer = DM_TIME_LIMIT if mode == DEATHMATCH else TDM_TIME_LIMIT
        self.dm_respawn_timers: list[float] = [0.0] * 10
        if self.mode == SPIKERUSH:
            self._sr_setup_round()
        if self.mode == "teamdeathmatch":
            self.phase = RoundPhase.ACTION
            self.phase_timer = TDM_TIME_LIMIT
            for p in self.world.players:
                p.grant_weapon("classic")

    # ------------------------------------------------------------------ #
    def _buy_time_for_round(self, round_number: int) -> float:
        if self.mode in ("deathmatch", "teamdeathmatch") or self.rules is None:
            return BUY_TIME_FIRST
        if round_number == 1 or (self.rules.half_rounds and round_number == self.rules.half_rounds + 1):
            return self.rules.buy_time_first
        return self.rules.buy_time_normal

    def _round_in_half(self) -> int:
        """半場內第幾回合（1-based）。"""
        if self.rules is None or not self.rules.half_rounds:
            return self.round
        return (self.round - 1) % self.rules.half_rounds + 1

    def _sr_setup_round(self) -> None:
        """Spike Rush 回合開始：全場配裝＋護甲＋技能補滿＋orbs。"""
        rih = self._round_in_half()
        self.sr_loadout = sr_round_weapon(self.world.rng, rih)
        shield = sr_round_shield(rih)
        for p in self.world.players:
            p.grant_weapon(self.sr_loadout)
            p.grant_shield(float(shield))
            p.abilities.refill()
            p.new_round()
        self.orb_field.spawn_for_round(self.world.rng, self.world.map_data, self.round)
        self.event_log.append(f"sr: round{self.round} loadout={self.sr_loadout} shield={shield} orbs={len(self.orb_field.orbs)}")

    # ------------------------------------------------------------------ #
    def attackers(self, round_number: int | None = None) -> int:
        r = self.round if round_number is None else round_number
        half = self.rules.half_rounds if self.rules is not None else ROUNDS_PER_HALF
        if not half:
            return TEAM_ATTACKERS
        return TEAM_ATTACKERS if (r - 1) % (half * 2) < half else TEAM_DEFENDERS

    def defenders(self) -> int:
        return 1 - self.attackers()

    def attacker_team_players(self) -> list[int]:
        a = self.attackers()
        return [i for i, p in enumerate(self.world.players) if p.team == a]

    # ------------------------------------------------------------------ #
    def step(self, dt: float) -> None:
        if self.phase == RoundPhase.FINISHED:
            return
        if self.mode in ("deathmatch", "teamdeathmatch"):
            self._step_deathmatch(dt)
            return
        self.phase_timer -= dt
        if self.phase == RoundPhase.BUY:
            if self.phase_timer <= 0.0:
                self._start_action()
        elif self.phase == RoundPhase.ACTION:
            self._check_round_end()
            if self.mode == SPIKERUSH:
                for ev in self.orb_field.update(self.world):
                    self.world.event_log.append(ev)
                    self.event_log.append(ev)
        elif self.phase == RoundPhase.END:
            if self.phase_timer <= 0.0:
                self._settle_and_next_round()

    def _step_deathmatch(self, dt: float) -> None:
        """死鬥/團隊死鬥：擊殺得分，團隊死鬥 100 殺或 300s、死鬥 40 殺或 540s。"""
        self.dm_timer -= dt
        for i in range(len(self.dm_respawn_timers)):
            if self.dm_respawn_timers[i] > 0:
                self.dm_respawn_timers[i] -= dt
                if self.dm_respawn_timers[i] <= 0:
                    self._respawn_player(i)
        if self.mode == "teamdeathmatch":
            for team in (0, 1):
                if self.tdm_team_kills[team] >= TDM_KILLS_TO_WIN:
                    self.phase = RoundPhase.FINISHED
                    self.round_reason = f"team{team} reached {TDM_KILLS_TO_WIN} kills"
                    self.event_log.append(self.round_reason)
                    return
            if self.dm_timer <= 0:
                winner = 0 if self.tdm_team_kills[0] >= self.tdm_team_kills[1] else 1
                self.phase = RoundPhase.FINISHED
                self.round_reason = f"time up, team{winner} wins {self.tdm_team_kills[winner]}-{self.tdm_team_kills[1-winner]}"
                self.event_log.append(self.round_reason)
            return
        for i, kills in enumerate(self.dm_kill_counts):
            if kills >= DM_KILLS_TO_WIN:
                self.phase = RoundPhase.FINISHED
                self.round_reason = f"player{i} reached {DM_KILLS_TO_WIN} kills"
                self.event_log.append(self.round_reason)
                return
        if self.dm_timer <= 0:
            winner = self.dm_kill_counts.index(max(self.dm_kill_counts))
            self.phase = RoundPhase.FINISHED
            self.round_reason = f"time up, player{winner} wins with {self.dm_kill_counts[winner]} kills"
            self.event_log.append(self.round_reason)

    def _respawn_player(self, slot: int) -> None:
        """死鬥模式復活。"""
        p = self.world.players[slot]
        p.alive = True
        p.health = 100
        p.shield_hp = 0
        # 隨機重生點
        spawns = self.world.map_data.get("spawns_attackers", []) + self.world.map_data.get("spawns_defenders", [])
        if spawns:
            sp = self.world.rng.choice(spawns)
            p.pos = Vec3(sp["x"], sp["y"], sp["z"])
        self.event_log.append(f"dm: player{slot} respawned")

    # ------------------------------------------------------------------ #
    def _start_action(self) -> None:
        self.phase = RoundPhase.ACTION
        self.phase_timer = self.rules.action_time if self.rules is not None else ACTION_TIME
        self.event_log.append(f"round{self.round} action start (attackers=team{self.attackers()})")

    def _check_round_end(self) -> None:
        a = self.attackers()
        d = self.defenders()
        alive_a = sum(1 for i, p in enumerate(self.world.players) if p.team == a and p.alive)
        alive_d = sum(1 for i, p in enumerate(self.world.players) if p.team == d and p.alive)
        spike = self.world.spike

        if spike is not None and spike.state.value == "detonated":
            self._end_round(a, "spike_detonated")
            return
        if spike is not None and spike.state.value == "defused":
            self._end_round(d, "spike_defused")
            return
        if alive_a == 0:
            self._end_round(d, "attackers_eliminated")
            return
        if alive_d == 0:
            self._end_round(a, "defenders_eliminated")
            return
        # 時間到：Spike 已安放且未解決 → 等 Spike 解決；否則守方勝
        if self.phase_timer <= 0.0:
            if spike is None or spike.state.value != "planted":
                self._end_round(d, "round_timeout")
            else:
                self.phase_timer = 0.0   # 停錶，等 Spike 爆炸或拆除

    def _end_round(self, winner: int, reason: str) -> None:
        self.phase = RoundPhase.END
        self.phase_timer = END_TIME
        self.round_winner = winner
        self.round_reason = reason
        self.scores[winner] += 1
        self.loss_streak[winner] = 0
        self.loss_streak[1 - winner] += 1
        self.round_records.append(RoundRecord(self.round, winner, reason))
        self.event_log.append(f"round{self.round} -> team{winner} wins ({reason})")
        # 終點球：敗方每人 +1（贏方不給，靠擊殺/助攻/安放自己挣）
        from server.game.entities import ULT_POINTS_ROUND_LOSS
        for _i, _pl in enumerate(self.world.players):
            if _pl.team != winner:
                self.world.award_ult(_i, ULT_POINTS_ROUND_LOSS, "round_loss")

    def _settle_and_next_round(self) -> None:
        # 經濟結算（依模式）
        if self.mode == SWIFTPLAY:
            # 固定配給：依半場內回合數＋上回合是否獲勝
            rih_next = self._round_in_half() + 1
            for p in self.world.players:
                won_prev = (p.team == self.round_winner)
                p.economy.credits = min(9000, sp_round_grant(rih_next, won_prev))
            self._sp_prev_winner = self.round_winner
        elif self.mode == SPIKERUSH:
            pass  # 配裝制：無經濟
        else:
            # 標準：勝隊 +3000，敗隊連敗補償（含最終回合）
            for i, p in enumerate(self.world.players):
                team = p.team
                if team == self.round_winner:
                    p.economy.grant(ROUND_WIN_REWARD)
                else:
                    p.economy.grant(loss_bonus(self.loss_streak[team]))
        # 獲勝判定
        if self.rules is not None:
            win_threshold = self.rules.rounds_to_win
            ot_tag = ""
            if self.mode == COMPETITIVE and self.scores[0] == 12 and self.scores[1] == 12:
                win_threshold = ROUNDS_OVERTIME
                ot_tag = " (OT)"
        else:
            win_threshold, ot_tag = ROUNDS_TO_WIN, ""
        if self.scores[self.round_winner] >= win_threshold:
            self.phase = RoundPhase.FINISHED
            self.event_log.append(
                f"MATCH END{ot_tag}: team{self.round_winner} wins "
                f"{self.scores[self.round_winner]}-{self.scores[1 - self.round_winner]}"
            )
            return
        self.round += 1
        self._reset_round_state()
        self.round_winner = None
        self.phase = RoundPhase.BUY
        self.phase_timer = self._buy_time_for_round(self.round)
        if self.mode == SPIKERUSH:
            self._sr_setup_round()

    def _reset_round_state(self) -> None:
        """回合重置：重生、血量、彈匣；保留武器與護甲；Spike 重置。"""
        a = self.attackers()
        spawns = self.world.map_data.spawns_attackers if a == TEAM_ATTACKERS else self.world.map_data.spawns_defenders
        slots_a = [i for i, p in enumerate(self.world.players) if p.team == a]
        slots_d = [i for i, p in enumerate(self.world.players) if p.team != a]
        for idx, slot in enumerate(slots_a + slots_d):
            p = self.world.players[slot]
            p.alive = True
            p.health = 100.0
            p.pos = spawns[idx % len(spawns)]
            p.vel = Vec3()
            p.inventory.reset_all()
            p.status.statuses.clear()
            p.new_round()
        if self.world.spike is not None:
            self.world.spike.reset()
        self.world.projectiles.clear()
        self.world.deployables.clear()
        self.world.smokes.clear()

    def scoreboard(self) -> dict:
        return {
            "round": self.round,
            "phase": self.phase.value,
            "scores": dict(self.scores),
            "records": [{"n": r.number, "w": r.winner, "r": r.reason} for r in self.round_records],
        }

    # ──── Match result tracking ────

    def build_match_result(self, match_id: str = "") -> MatchResult:
        result = MatchResult(
            match_id=match_id or f"match_{self.round}_{id(self)}",
            winner=self.round_winner if self.round_winner is not None else -1,
            scores=dict(self.scores),
            total_rounds=self.round,
            round_records=[{"n": r.number, "w": r.winner, "r": r.reason} for r in self.round_records],
            is_ranked=self.mode == "competitive",
        )
        for i, p in enumerate(self.world.players):
            stats = PlayerMatchStats(
                player_id=i,
                team=p.team,
                kills=getattr(p, "kills", 0),
                deaths=getattr(p, "deaths", 0),
                assists=getattr(p, "assists", 0),
                damage=getattr(p, "damage_dealt", 0),
                first_kills=getattr(p, "first_kills", 0),
                first_deaths=getattr(p, "first_deaths", 0),
                plants=getattr(p, "plants", 0),
                defuses=getattr(p, "defuses", 0),
                economy=p.economy.credits if hasattr(p, "economy") else 0,
                alive=p.alive,
            )
            stats.compute_score()
            result.player_stats[i] = stats
        return result

    def apply_ranked_changes(self, match_result: MatchResult, ranked_system) -> dict:
        if not match_result.is_ranked or match_result.winner < 0:
            return {}

        winner_ids = [str(s.player_id) for s in match_result.get_team_stats(match_result.winner)]
        loser_ids = [str(s.player_id) for s in match_result.get_team_stats(1 - match_result.winner)]

        winner_elos = []
        loser_elos = []
        for pid in winner_ids:
            pr = ranked_system.get_or_create(pid)
            winner_elos.append(pr.elo)
        for pid in loser_ids:
            pr = ranked_system.get_or_create(pid)
            loser_elos.append(pr.elo)

        elo_results = ranked_system.process_match_result(
            winner_ids, loser_ids, winner_elos, loser_elos
        )
        match_result.elo_changes = elo_results
        return elo_results

    def get_round_records_raw(self) -> list[dict]:
        return [{"n": r.number, "w": r.winner, "r": r.reason} for r in self.round_records]
