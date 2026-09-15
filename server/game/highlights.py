"""
server/game/highlights.py — 高光時刻追蹤（對標 Valorant 好玩原則 P4）
===================================================================
* 連殺播報：Double / Triple / Quad / ACE（同回合同一人擊殺數）
* 殘局（Clutch）：回合勝利時，勝方最後僅剩 1 人存活 → 1vX 殘局
* 首殺（First Blood）：每回合第一次擊殺
* Play of the Match：整場最高分回合表現
  計分：ACE 100 / 4殺 60 / 3殺 30 / 2殺 10 / 殘局加成 +15×敵方人數 / 首殺 +5

Tracker 掃描 world.event_log（"kill: slotV by slotK (w)"）增量解析，
零侵入：不改 World/Match 熱路徑，測試與實戰皆可手動 update(world, match)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

STREAK_NAMES = {2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "QUAD KILL", 5: "ACE"}


@dataclass
class RoundHighlight:
    round: int
    player: int
    kills: int
    streak_name: str = ""
    clutch_vs: int = 0       # 殘局時敵方人數（0 = 非殘局）
    first_blood: bool = False
    score: int = 0


@dataclass
class PlayOfMatch:
    round: int = 0
    player: int = -1
    kills: int = 0
    streak_name: str = ""
    clutch_vs: int = 0
    score: int = 0


class HighlightTracker:
    def __init__(self):
        self._seen_log = 0
        self._round_kills: dict[int, list[int]] = {}  # round -> [killer slots...]
        self._first_blood: dict[int, int] = {}        # round -> killer slot
        self._round_start_alive: dict[int, dict[int, int]] = {}  # round -> {team: alive}
        self._round_min_alive: dict[int, dict[int, int]] = {}    # round -> {team: 最小存活數}
        self.round_highlights: list[RoundHighlight] = []
        self._done_rounds: set[int] = set()

    # ------------------------------------------------------------------ #
    def update(self, world, match) -> list[str]:
        """掃描新增事件＋結算已結束回合。回傳播報字串。"""
        announcements: list[str] = []
        rnd = match.round
        if rnd not in self._round_start_alive:
            self._round_start_alive[rnd] = {
                0: sum(1 for p in world.players if p.team == 0 and p.alive),
                1: sum(1 for p in world.players if p.team == 1 and p.alive),
            }
        # 回合中最小存活數（結算在重置後發生，屆時全員已復活，故需即時追蹤）
        cur = {
            0: sum(1 for p in world.players if p.team == 0 and p.alive),
            1: sum(1 for p in world.players if p.team == 1 and p.alive),
        }
        prev = self._round_min_alive.get(rnd)
        if prev is None:
            self._round_min_alive[rnd] = dict(cur)
        else:
            self._round_min_alive[rnd] = {t: min(prev[t], cur[t]) for t in (0, 1)}
        for line in world.event_log[self._seen_log:]:
            if line.startswith("kill: slot"):
                try:
                    # "kill: slotV by slotK (weapon)"
                    rest = line[len("kill: slot"):]
                    v_str, rest = rest.split(" by slot", 1)
                    k_str = rest.split(" ", 1)[0]
                    v, k = int(v_str), int(k_str)
                except (ValueError, IndexError):
                    continue
                if k < 0:
                    continue
                self._round_kills.setdefault(rnd, []).append(k)
                if rnd not in self._first_blood:
                    self._first_blood[rnd] = k
                    announcements.append(f"first_blood: round{rnd} slot{k}")
                n = self._round_kills[rnd].count(k)
                if n in STREAK_NAMES:
                    announcements.append(f"streak: round{rnd} slot{k} {STREAK_NAMES[n]}")
        self._seen_log = len(world.event_log)
        # 結算：round_records 中出現但尚未結算的回合
        for rec in match.round_records:
            if rec.number in self._done_rounds:
                continue
            self._done_rounds.add(rec.number)
            announcements.extend(self._settle_round(world, match, rec.number, rec.winner))
        return announcements

    def _settle_round(self, world, match, rnd: int, winner: int | None) -> list[str]:
        out: list[str] = []
        if winner is None:
            return out
        kills = self._round_kills.get(rnd, [])
        if not kills:
            return out
        from collections import Counter
        counts = Counter(kills)
        # 勝方回合中最小存活數（殘局判定；結算時已重置故不能看當下）
        min_alive = self._round_min_alive.get(rnd, {})
        alive_win = min_alive.get(winner, 99)
        start = self._round_start_alive.get(rnd, {})
        enemies_start = start.get(1 - winner, 0)
        for slot, n in counts.items():
            if world.players[slot].team != winner:
                continue
            hl = RoundHighlight(round=rnd, player=slot, kills=n)
            if n in STREAK_NAMES:
                hl.streak_name = STREAK_NAMES[n]
                hl.score += {2: 10, 3: 30, 4: 60, 5: 100}[n]
            if self._first_blood.get(rnd) == slot:
                hl.first_blood = True
                hl.score += 5
            if alive_win == 1 and enemies_start >= 2:
                hl.clutch_vs = enemies_start
                hl.score += 15 * enemies_start
                out.append(f"clutch: round{rnd} slot{slot} 1v{enemies_start}")
            if hl.score > 0:
                self.round_highlights.append(hl)
        return out

    # ------------------------------------------------------------------ #
    def play_of_match(self) -> PlayOfMatch:
        best = PlayOfMatch()
        for hl in self.round_highlights:
            if hl.score > best.score:
                best = PlayOfMatch(round=hl.round, player=hl.player, kills=hl.kills,
                                   streak_name=hl.streak_name, clutch_vs=hl.clutch_vs,
                                   score=hl.score)
        return best
