"""
server/game/history.py — Match History (last 10 per player)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class HistoryRecord:
    match_id: str
    mode: str
    date: str
    won: bool
    score_atk: int
    score_def: int
    kills: int
    deaths: int
    assists: int
    agent: str
    map_name: str
    rr_change: int = 0

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "mode": self.mode,
            "date": self.date,
            "won": self.won,
            "score_atk": self.score_atk,
            "score_def": self.score_def,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "agent": self.agent,
            "map_name": self.map_name,
            "rr_change": self.rr_change,
        }

    @staticmethod
    def from_dict(d: dict) -> HistoryRecord:
        return HistoryRecord(
            match_id=d["match_id"],
            mode=d["mode"],
            date=d["date"],
            won=d["won"],
            score_atk=d["score_atk"],
            score_def=d["score_def"],
            kills=d["kills"],
            deaths=d["deaths"],
            assists=d["assists"],
            agent=d["agent"],
            map_name=d["map_name"],
            rr_change=d.get("rr_change", 0),
        )


class MatchHistory:
    def __init__(self, max_records: int = 10):
        self.records: list[HistoryRecord] = []
        self.max = max_records

    def add(self, record: HistoryRecord) -> None:
        self.records.insert(0, record)
        self.records = self.records[:self.max]

    def get(self, count: int = 10) -> list[HistoryRecord]:
        return self.records[:count]

    def to_dict(self) -> dict:
        return {"records": [r.to_dict() for r in self.records], "max": self.max}

    @staticmethod
    def from_dict(d: dict) -> MatchHistory:
        mh = MatchHistory(max_records=d.get("max", 10))
        mh.records = [HistoryRecord.from_dict(r) for r in d.get("records", [])]
        return mh
