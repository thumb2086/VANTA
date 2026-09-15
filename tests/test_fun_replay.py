"""
tests/test_fun_replay.py — 回放 MVP 驗收（錄製→存檔→回放 round-trip）
====================================================================
對應 docs/valorant_patch_research.md P4、docs/REPLAY_SYSTEM_DESIGN.md。
"""

import os
import tempfile

from server.core.movement import MoveInput
from server.game.entities import World
from server.game.replay import ReplayPlayer, ReplayRecorder


def _sim_match(ticks: int = 64):
    w = World()
    m = w.start_match(mode="competitive")
    rec = ReplayRecorder()
    rec.record_meta("test_match_1", "competitive", "default")
    for t in range(ticks):
        ins = []
        for i, p in enumerate(w.players):
            mv = MoveInput(forward=1.0 if i % 2 == 0 else 0.0)
            ins.append(mv)
        w.step(ins, 1.0 / 128.0)
        rec.record_tick(w.tick, w.time, w)
        if t == 10:
            rec.record_event(w.tick, "kill", {"killer": 0, "victim": 5, "weapon": "vandal"})
        if t == 20:
            rec.record_event(w.tick, "plant", {"slot": 0, "site": "A"})
    rec.finish(winner=0, scores={0: 1, 1: 0})
    return rec, w


def test_record_tick_count_and_shape():
    rec, w = _sim_match(64)
    assert len(rec.ticks) == 64
    t0 = rec.ticks[0]
    assert set(t0) == {"tick", "t", "players", "spike"}
    assert len(t0["players"]) == len(w.players)
    p0 = t0["players"][0]
    assert set(p0) == {"slot", "team", "pos", "hp", "alive", "weapon"}
    assert len(p0["pos"]) == 3


def test_positions_advance_over_time():
    rec, w = _sim_match(64)
    z0 = rec.ticks[0]["players"][0]["pos"][2]
    z1 = rec.ticks[-1]["players"][0]["pos"][2]
    assert z1 > z0, "前進玩家 z 應增加"


def test_save_load_roundtrip():
    rec, _ = _sim_match(32)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rep1")
        rec.save(path)
        assert os.path.isfile(os.path.join(path, "meta.json"))
        assert os.path.isfile(os.path.join(path, "ticks.jsonl"))
        assert os.path.isfile(os.path.join(path, "events.jsonl"))
        pl = ReplayPlayer()
        pl.load(path)
        assert pl.meta["match_id"] == "test_match_1"
        assert pl.meta["winner"] == 0
        assert len(pl.ticks) == 32
        assert pl.ticks == rec.ticks
        assert pl.events == rec.events


def test_state_at_and_events_between():
    rec, _ = _sim_match(64)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rep1")
        rec.save(path)
        pl = ReplayPlayer()
        pl.load(path)
        s = pl.state_at(20)
        assert s is not None and s["tick"] <= 20
        assert pl.state_at(0) is None  # tick 從 1 開始
        evs = pl.events_between(0, 10**9)
        assert {e["kind"] for e in evs} == {"kill", "plant"}
        kill = pl.jump_to_event("kill")
        assert kill is not None and kill["killer"] == 0 and kill["victim"] == 5
        assert pl.jump_to_event("ace") is None
        assert pl.jump_to_event("kill", 5) is None
        assert pl.event_kinds() == ["kill", "plant"]
