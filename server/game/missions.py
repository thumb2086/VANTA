"""
server/game/missions.py — 每日任務＋XP（對標 Valorant 好玩原則 P5）
===================================================================
* 每天（UTC 日期種子）發 3 個任務，任務池 8 種
* record(event, amount) 累積進度；完成即發 XP（可重複領取判定由呼叫端）
* XP 等級：level = xp // 1000 + 1
* to_dict/from_dict 持久化

事件種類：kill / death / assist / plant / defuse / round_win / match_end / match_win / damage
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

XP_PER_LEVEL = 1000


@dataclass(frozen=True)
class MissionDef:
    key: str
    desc: str
    event: str
    target: int
    xp: int


MISSION_POOL: tuple[MissionDef, ...] = (
    MissionDef("kill_10", "拿下 10 次擊殺", "kill", 10, 500),
    MissionDef("kill_25", "拿下 25 次擊殺", "kill", 25, 1000),
    MissionDef("damage_2000", "造成 2000 點傷害", "damage", 2000, 500),
    MissionDef("assist_5", "獲得 5 次助攻", "assist", 5, 500),
    MissionDef("plant_2", "安放 2 次 Spike", "plant", 2, 750),
    MissionDef("defuse_1", "拆除 1 次 Spike", "defuse", 1, 750),
    MissionDef("win_3_rounds", "贏得 3 回合", "round_win", 3, 500),
    MissionDef("play_2", "完成 2 場對戰", "match_end", 2, 1000),
)

DAILY_COUNT = 3


def daily_missions(date_str: str) -> list[MissionDef]:
    """UTC 日期（YYYY-MM-DD）→ 當日 3 任務（確定性）。"""
    h = int(hashlib.sha256(date_str.encode()).hexdigest(), 16)
    # 簡單確定性排序：依 hash 取前 3
    order = sorted(range(len(MISSION_POOL)), key=lambda i: (h // (7 + i)) % 100003)
    return [MISSION_POOL[i] for i in order[:DAILY_COUNT]]


@dataclass
class MissionProgress:
    key: str
    progress: int = 0
    claimed: bool = False

    def add(self, amount: int, target: int) -> bool:
        """累積進度。回傳是否剛完成。"""
        was_done = self.progress >= target
        self.progress = min(target, self.progress + amount)
        return (not was_done) and self.progress >= target


class MissionTracker:
    def __init__(self, date_str: str):
        self.date = date_str
        self.defs: dict[str, MissionDef] = {m.key: m for m in daily_missions(date_str)}
        self.progress: dict[str, MissionProgress] = {k: MissionProgress(k) for k in self.defs}
        self.xp = 0

    @property
    def level(self) -> int:
        return self.xp // XP_PER_LEVEL + 1

    def record(self, event: str, amount: int = 1) -> list[str]:
        """記錄事件。回傳剛完成的任務 key 列表（呼叫端發 XP 橫幅）。"""
        done: list[str] = []
        for key, d in self.defs.items():
            if d.event != event:
                continue
            if self.progress[key].add(amount, d.target):
                self.xp += d.xp
                done.append(key)
        return done

    def summary(self) -> list[dict]:
        return [
            {"key": k, "desc": d.desc, "progress": self.progress[k].progress,
             "target": d.target, "xp": d.xp, "claimed": self.progress[k].claimed}
            for k, d in self.defs.items()
        ]

    def to_dict(self) -> dict:
        return {"date": self.date, "xp": self.xp,
                "progress": {k: {"p": v.progress, "c": v.claimed} for k, v in self.progress.items()}}

    @staticmethod
    def from_dict(data: dict) -> "MissionTracker":
        t = MissionTracker(data["date"])
        t.xp = data.get("xp", 0)
        for k, v in data.get("progress", {}).items():
            if k in t.progress:
                t.progress[k].progress = v.get("p", 0)
                t.progress[k].claimed = v.get("c", False)
        return t
