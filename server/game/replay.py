"""
server/game/replay.py — 回放 MVP 資料層（對標 Valorant 11.06 重播，好玩原則 P4）
================================================================================
對齊 docs/REPLAY_SYSTEM_DESIGN.md 的精簡實作：
* ReplayRecorder：record_meta / record_tick(world 輕量快照) / record_event
* 存檔：meta.json + ticks.jsonl + events.jsonl（目錄）
* ReplayPlayer：load / state_at(tick) / events_between / jump_to_event(kind)
* tick 快照只保留回放必要欄位（slot/team/pos/hp/alive/weapon），128Hz 全量錄
  一場 30 分鐘 ≈ 230k ticks — MVP 不壓縮，實戰可再抽稀（見 FUTURE）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class ReplayMeta:
    match_id: str = ""
    mode: str = "competitive"
    map: str = "default"
    winner: int = -1
    scores: dict = field(default_factory=dict)
    total_ticks: int = 0


class ReplayRecorder:
    def __init__(self):
        self.meta = ReplayMeta()
        self.ticks: list[dict] = []
        self.events: list[dict] = []

    def record_meta(self, match_id: str, mode: str, map_name: str = "default") -> None:
        self.meta.match_id = match_id
        self.meta.mode = mode
        self.meta.map = map_name

    def record_tick(self, tick: int, time_s: float, world) -> None:
        players = []
        for p in world.players:
            w = p.inventory.active_state()
            key = w.stats.key if hasattr(w, "stats") else "classic"
            players.append({
                "slot": p.slot, "team": p.team,
                "pos": [round(p.pos.x, 3), round(p.pos.y, 3), round(p.pos.z, 3)],
                "hp": round(p.health, 1), "alive": p.alive, "weapon": key,
            })
        spike = None
        if getattr(world, "spike", None) is not None:
            spike = world.spike.state.value
        self.ticks.append({"tick": tick, "t": round(time_s, 4), "players": players, "spike": spike})

    def record_event(self, tick: int, kind: str, payload: dict) -> None:
        """kind: kill / plant / defuse / round_end / orb / assist / streak / clutch ..."""
        self.events.append({"tick": tick, "kind": kind, **payload})

    def finish(self, winner: int, scores: dict) -> None:
        self.meta.winner = winner
        self.meta.scores = dict(scores)
        self.meta.total_ticks = len(self.ticks)

    def save(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta.__dict__, f, ensure_ascii=False)
        with open(os.path.join(path, "ticks.jsonl"), "w", encoding="utf-8") as f:
            for t in self.ticks:
                f.write(json.dumps(t) + "\n")
        with open(os.path.join(path, "events.jsonl"), "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e) + "\n")


class ReplayPlayer:
    def __init__(self):
        self.meta: dict = {}
        self.ticks: list[dict] = []
        self.events: list[dict] = []

    def load(self, path: str) -> None:
        with open(os.path.join(path, "meta.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self.ticks = []
        with open(os.path.join(path, "ticks.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.ticks.append(json.loads(line))
        self.events = []
        with open(os.path.join(path, "events.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.events.append(json.loads(line))

    def state_at(self, tick: int) -> dict | None:
        """回放定位：取 tick ≤ 目標的最大快照（無則 None）。"""
        best = None
        for t in self.ticks:
            if t["tick"] <= tick:
                best = t
            else:
                break
        return best

    def events_between(self, tick_from: int, tick_to: int) -> list[dict]:
        return [e for e in self.events if tick_from <= e["tick"] <= tick_to]

    def jump_to_event(self, kind: str, index: int = 0) -> dict | None:
        """跳到第 index 個指定 kind 事件（如第 2 個 kill）。"""
        found = [e for e in self.events if e["kind"] == kind]
        if not found or not (0 <= index < len(found)):
            return None
        return found[index]

    def event_kinds(self) -> list[str]:
        seen: list[str] = []
        for e in self.events:
            if e["kind"] not in seen:
                seen.append(e["kind"])
        return seen
