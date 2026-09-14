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


class Match:
    def __init__(self, world, config=None, mode: str = "competitive"):
        self.world = world
        self.mode = mode  # competitive / deathmatch
        self.phase = RoundPhase.BUY
        self.round = 1
        self.scores = {0: 0, 1: 0}
        self.loss_streak = {0: 0, 1: 0}
        self.phase_timer = BUY_TIME_FIRST
        self.round_records: list[RoundRecord] = []
        self.round_winner: int | None = None
        self.round_reason = ""
        self.event_log: list[str] = []
        # 死鬥模式
        self.dm_kill_counts: list[int] = [0] * 10  # 每人擊殺數
        self.dm_timer = DM_TIME_LIMIT
        self.dm_respawn_timers: list[float] = [0.0] * 10  # 復活倒數

    # ------------------------------------------------------------------ #
    def attackers(self, round_number: int | None = None) -> int:
        r = self.round if round_number is None else round_number
        return TEAM_ATTACKERS if (r - 1) % (ROUNDS_PER_HALF * 2) < ROUNDS_PER_HALF else TEAM_DEFENDERS

    def defenders(self) -> int:
        return 1 - self.attackers()

    def attacker_team_players(self) -> list[int]:
        a = self.attackers()
        return [i for i, p in enumerate(self.world.players) if p.team == a]

    # ------------------------------------------------------------------ #
    def step(self, dt: float) -> None:
        if self.phase == RoundPhase.FINISHED:
            return
        if self.mode == "deathmatch":
            self._step_deathmatch(dt)
            return
        self.phase_timer -= dt
        if self.phase == RoundPhase.BUY:
            if self.phase_timer <= 0.0:
                self._start_action()
        elif self.phase == RoundPhase.ACTION:
            self._check_round_end()
        elif self.phase == RoundPhase.END:
            if self.phase_timer <= 0.0:
                self._settle_and_next_round()

    def _step_deathmatch(self, dt: float) -> None:
        """死鬥模式：無回合，擊殺得分，20 殺或 10 分鐘結束。"""
        self.dm_timer -= dt
        # 復活計時
        for i in range(len(self.dm_respawn_timers)):
            if self.dm_respawn_timers[i] > 0:
                self.dm_respawn_timers[i] -= dt
                if self.dm_respawn_timers[i] <= 0:
                    self._respawn_player(i)
        # 檢查勝利條件
        for i, kills in enumerate(self.dm_kill_counts):
            if kills >= DM_KILLS_TO_WIN:
                self.phase = RoundPhase.FINISHED
                self.round_reason = f"player{i} reached {DM_KILLS_TO_WIN} kills"
                self.event_log.append(self.round_reason)
                return
        if self.dm_timer <= 0:
            # 時間到，最高分者勝
            winner = self.dm_kill_counts.index(max(self.dm_kill_counts))
            self.phase = RoundPhase.FINISHED
            self.round_reason = f"time up, player{winner} wins with {self.dm_kill_counts[winner]} kills"
            self.event_log.append(self.round_reason)

    def _respawn_player(self, slot: int) -> None:
        """死鬥模式復活。"""
        import random
        p = self.world.players[slot]
        p.alive = True
        p.health = 100
        p.shield_hp = 0
        # 隨機重生點
        spawns = self.world.map_data.get("spawns_attackers", []) + self.world.map_data.get("spawns_defenders", [])
        if spawns:
            sp = random.choice(spawns)
            p.pos = Vec3(sp["x"], sp["y"], sp["z"])
        self.event_log.append(f"dm: player{slot} respawned")

    # ------------------------------------------------------------------ #
    def _start_action(self) -> None:
        self.phase = RoundPhase.ACTION
        self.phase_timer = ACTION_TIME
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

    def _settle_and_next_round(self) -> None:
        # 經濟結算：勝隊 +3000，敗隊連敗補償（含最終回合）
        for i, p in enumerate(self.world.players):
            team = p.team
            if team == self.round_winner:
                p.economy.grant(ROUND_WIN_REWARD)
            else:
                p.economy.grant(loss_bonus(self.loss_streak[team]))
        # 獲勝判定：正規先到 13 分；12-12 時進入延長賽，先到 14 分勝
        win_threshold = ROUNDS_OVERTIME if (self.scores[0] == 12 and self.scores[1] == 12) else ROUNDS_TO_WIN
        if self.scores[self.round_winner] >= win_threshold:
            self.phase = RoundPhase.FINISHED
            ot_tag = " (OT)" if win_threshold == ROUNDS_OVERTIME else ""
            self.event_log.append(
                f"MATCH END{ot_tag}: team{self.round_winner} wins "
                f"{self.scores[self.round_winner]}-{self.scores[1 - self.round_winner]}"
            )
            return
        self.round += 1
        self._reset_round_state()
        self.round_winner = None
        self.phase = RoundPhase.BUY
        self.phase_timer = BUY_TIME_FIRST if self.round in (1, ROUNDS_PER_HALF + 1) else BUY_TIME_NORMAL

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
