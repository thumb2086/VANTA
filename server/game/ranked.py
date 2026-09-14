"""
server/game/ranked.py — ELO ranking system
===========================================
Ranks: Iron 1-3, Bronze 1-3, Silver 1-3, Gold 1-3, Platinum 1-3,
       Diamond 1-3, Ascendant 1-3, Immortal 1-3, Radiant
ELO: K=32, expected score, RR thresholds.
Placement: 5 provisional matches, start ELO 1500.
Matchmaking: ±200 ELO, expands ±50/10s.
Rank decay: 14 days inactive → -50 RR/day (min Iron 1).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

# ──── Rank definitions ────

RANKS = [
    ("Iron", 1), ("Iron", 2), ("Iron", 3),
    ("Bronze", 1), ("Bronze", 2), ("Bronze", 3),
    ("Silver", 1), ("Silver", 2), ("Silver", 3),
    ("Gold", 1), ("Gold", 2), ("Gold", 3),
    ("Platinum", 1), ("Platinum", 2), ("Platinum", 3),
    ("Diamond", 1), ("Diamond", 2), ("Diamond", 3),
    ("Ascendant", 1), ("Ascendant", 2), ("Ascendant", 3),
    ("Immortal", 1), ("Immortal", 2), ("Immortal", 3),
    ("Radiant", 1),
]

RANK_SYMBOLS = {
    "Iron": "\u2B21",
    "Bronze": "\u2B22",
    "Silver": "\u2B23",
    "Gold": "\u2B24",
    "Platinum": "\u2B25",
    "Diamond": "\u2B26",
    "Ascendant": "\u2726",
    "Immortal": "\u2727",
    "Radiant": "\u2605",
}

K_FACTOR = 32
STARTING_ELO = 1500
RR_PER_RANK = 100
PLACEMENT_MATCHES = 5
BASE_MMR_RANGE = 200
MMR_EXPAND_PER_SEC = 5.0
RANK_DECAY_INACTIVE_DAYS = 14
RANK_DECAY_RR_PER_DAY = 50
MIN_RANK_INDEX = 0  # Iron 1


@dataclass
class PlayerRank:
    player_id: str
    elo: int = STARTING_ELO
    rr: int = 0
    rank_index: int = 0
    wins: int = 0
    losses: int = 0
    placement_games: int = 0
    last_active: float = 0.0
    history: list[dict] = field(default_factory=list)

    @property
    def rank_name(self) -> str:
        return RANKS[self.rank_index][0]

    @property
    def rank_tier(self) -> int:
        return RANKS[self.rank_index][1]

    @property
    def rank_symbol(self) -> str:
        return RANK_SYMBOLS.get(self.rank_name, "\u2B21")

    @property
    def is_placement(self) -> bool:
        return self.placement_games < PLACEMENT_MATCHES

    @property
    def display_string(self) -> str:
        return "%s %s %d RR" % (self.rank_symbol, self.rank_name + " " + str(self.rank_tier), self.rr)


class RankedSystem:
    def __init__(self):
        self.players: dict[str, PlayerRank] = {}
        self.queue: list[dict] = []
        self.match_history: list[dict] = []

    def get_or_create(self, player_id: str) -> PlayerRank:
        if player_id not in self.players:
            self.players[player_id] = PlayerRank(
                player_id=player_id,
                last_active=time.time()
            )
        return self.players[player_id]

    def update_activity(self, player_id: str) -> None:
        pr = self.get_or_create(player_id)
        pr.last_active = time.time()

    # ──── ELO calculation ────

    def expected_score(self, elo_a: int, elo_b: int) -> float:
        return 1.0 / (1.0 + math.pow(10, (elo_b - elo_a) / 400.0))

    def calculate_elo_change(self, winner_elo: int, loser_elo: int, is_draw: bool = False) -> tuple[int, int]:
        if is_draw:
            expected_w = self.expected_score(winner_elo, loser_elo)
            change = int(K_FACTOR * (0.5 - expected_w))
            return change, -change

        expected_w = self.expected_score(winner_elo, loser_elo)
        winner_change = int(K_FACTOR * (1.0 - expected_w))
        loser_change = int(K_FACTOR * (0.0 - (1.0 - expected_w)))
        return winner_change, loser_change

    # ──── RR calculation ────

    def calculate_rr_change(self, won: bool, elo_diff: int, is_placement: bool) -> int:
        if is_placement:
            if won:
                return 25
            return -15

        if won:
            if elo_diff > 100:
                return 30
            elif elo_diff > 0:
                return 25
            else:
                return 20
        else:
            if elo_diff < -100:
                return -25
            elif elo_diff < 0:
                return -20
            else:
                return -15

    # ──── Rank progression ────

    def apply_rr_change(self, pr: PlayerRank, rr_change: int) -> dict:
        old_rank = (pr.rank_name, pr.rank_tier)
        old_rr = pr.rr

        pr.rr += rr_change
        result = {"rr_change": rr_change, "rank_changed": False, "old_rank": old_rank, "new_rank": old_rank}

        if pr.rr >= RR_PER_RANK:
            if pr.rank_index < len(RANKS) - 1:
                pr.rank_index += 1
                pr.rr -= RR_PER_RANK
                result["rank_changed"] = True
                result["new_rank"] = (pr.rank_name, pr.rank_tier)
        elif pr.rr < 0:
            if pr.rank_index > MIN_RANK_INDEX:
                pr.rank_index -= 1
                pr.rr += RR_PER_RANK
                result["rank_changed"] = True
                result["new_rank"] = (pr.rank_name, pr.rank_tier)
            else:
                pr.rr = 0

        return result

    # ──── Match processing ────

    def process_match_result(self, winner_ids: list[str], loser_ids: list[str],
                             winner_elos: list[int], loser_elos: list[int]) -> dict:
        avg_winner_elo = sum(winner_elos) / len(winner_elos) if winner_elos else STARTING_ELO
        avg_loser_elo = sum(loser_elos) / len(loser_elos) if loser_elos else STARTING_ELO

        elo_diff = int(avg_winner_elo - avg_loser_elo)
        winner_change, loser_change = self.calculate_elo_change(
            int(avg_winner_elo), int(avg_loser_elo)
        )

        results = {"winners": [], "losers": []}

        for pid in winner_ids:
            pr = self.get_or_create(pid)
            is_pl = pr.is_placement
            if is_pl:
                pr.placement_games += 1
            else:
                pr.wins += 1

            actual_elo_change = winner_change
            pr.elo += actual_elo_change
            rr_change = self.calculate_rr_change(True, elo_diff, is_pl)
            rr_result = self.apply_rr_change(pr, rr_change)
            pr.last_active = time.time()

            entry = {
                "player_id": pid,
                "elo_change": actual_elo_change,
                "rr_change": rr_change,
                "new_elo": pr.elo,
                "new_rr": pr.rr,
                "rank": pr.rank_name,
                "tier": pr.rank_tier,
                "rank_changed": rr_result["rank_changed"],
            }
            pr.history.append(entry)
            if len(pr.history) > 20:
                pr.history = pr.history[-20:]
            results["winners"].append(entry)

        for pid in loser_ids:
            pr = self.get_or_create(pid)
            is_pl = pr.is_placement
            if is_pl:
                pr.placement_games += 1
            else:
                pr.losses += 1

            actual_elo_change = loser_change
            pr.elo += actual_elo_change
            rr_change = self.calculate_rr_change(False, elo_diff, is_pl)
            rr_result = self.apply_rr_change(pr, rr_change)
            pr.last_active = time.time()

            entry = {
                "player_id": pid,
                "elo_change": actual_elo_change,
                "rr_change": rr_change,
                "new_elo": pr.elo,
                "new_rr": pr.rr,
                "rank": pr.rank_name,
                "tier": pr.rank_tier,
                "rank_changed": rr_result["rank_changed"],
            }
            pr.history.append(entry)
            if len(pr.history) > 20:
                pr.history = pr.history[-20:]
            results["losers"].append(entry)

        self.match_history.append(results)
        if len(self.match_history) > 100:
            self.match_history = self.match_history[-100:]

        return results

    # ──── Placement ────

    def get_placement_result(self, pr: PlayerRank) -> dict:
        if not pr.is_placement:
            return {"status": "complete", "rank": pr.rank_name, "tier": pr.rank_tier}

        wins = sum(1 for h in pr.history[-PLACEMENT_MATCHES:] if h.get("rr_change", 0) > 0)
        return {
            "status": "placement",
            "games_played": pr.placement_games,
            "games_remaining": PLACEMENT_MATCHES - pr.placement_games,
            "wins": wins,
        }

    # ──── Matchmaking ────

    def queue_player(self, player_id: str) -> dict:
        pr = self.get_or_create(player_id)
        self.update_activity(player_id)

        for entry in self.queue:
            if entry["player_id"] == player_id:
                return {"status": "already_queued", "wait_time": entry.get("wait", 0)}

        entry = {"player_id": player_id, "elo": pr.elo, "queued_at": time.time(), "wait": 0}
        self.queue.append(entry)
        return {"status": "queued"}

    def dequeue_player(self, player_id: str) -> None:
        self.queue = [e for e in self.queue if e["player_id"] != player_id]

    def find_match(self) -> dict | None:
        now = time.time()
        for entry in self.queue:
            elapsed = now - entry["queued_at"]
            entry["wait"] = elapsed

        for i in range(len(self.queue)):
            for j in range(i + 1, len(self.queue)):
                a = self.queue[i]
                b = self.queue[j]
                if a["player_id"].startswith("bot_") or b["player_id"].startswith("bot_"):
                    continue
                elo_diff = abs(a["elo"] - b["elo"])
                max_range = BASE_MMR_RANGE + int(elapsed * MMR_EXPAND_PER_SEC)
                if elo_diff <= max_range:
                    match = {
                        "players": [a["player_id"], b["player_id"]],
                        "avg_elo": (a["elo"] + b["elo"]) // 2,
                        "elo_diff": elo_diff,
                    }
                    self.dequeue_player(a["player_id"])
                    self.dequeue_player(b["player_id"])
                    return match
        return None

    # ──── Rank decay ────

    def apply_decay(self) -> list[dict]:
        now = time.time()
        decayed = []
        for pr in self.players.values():
            if pr.last_active == 0:
                continue
            days_inactive = (now - pr.last_active) / 86400.0
            if days_inactive <= RANK_DECAY_INACTIVE_DAYS:
                continue
            decay_days = days_inactive - RANK_DECAY_INACTIVE_DAYS
            rr_loss = int(decay_days * RANK_DECAY_RR_PER_DAY)
            if rr_loss <= 0:
                continue
            result = self.apply_rr_change(pr, -rr_loss)
            pr.last_active = now
            decayed.append({
                "player_id": pr.player_id,
                "rr_lost": rr_loss,
                "new_rr": pr.rr,
                "rank": pr.rank_name,
                "tier": pr.rank_tier,
            })
        return decayed

    # ──── Serialization ────

    def serialize_player(self, player_id: str) -> dict:
        pr = self.get_or_create(player_id)
        return {
            "player_id": pr.player_id,
            "elo": pr.elo,
            "rr": pr.rr,
            "rank": pr.rank_name,
            "tier": pr.rank_tier,
            "symbol": pr.rank_symbol,
            "wins": pr.wins,
            "losses": pr.losses,
            "is_placement": pr.is_placement,
            "placement_games": pr.placement_games,
            "history": pr.history[-10:],
            "display": pr.display_string,
        }

    def get_leaderboard(self, limit: int = 50) -> list[dict]:
        sorted_players = sorted(self.players.values(), key=lambda p: (p.elo, p.rr), reverse=True)
        return [
            {
                "rank": i + 1,
                "player_id": p.player_id,
                "elo": p.elo,
                "rr": p.rr,
                "rank_name": p.rank_name,
                "tier": p.rank_tier,
                "wins": p.wins,
                "losses": p.losses,
            }
            for i, p in enumerate(sorted_players[:limit])
        ]
