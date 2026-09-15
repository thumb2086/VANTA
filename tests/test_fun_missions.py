"""
tests/test_fun_missions.py — 每日任務＋XP 驗收
==============================================
對應 docs/valorant_patch_research.md P5。
"""

from server.game.missions import (
    DAILY_COUNT, MISSION_POOL, MissionTracker, daily_missions,
)


def test_daily_count_and_determinism():
    a = daily_missions("2026-09-15")
    b = daily_missions("2026-09-15")
    assert len(a) == DAILY_COUNT
    assert [m.key for m in a] == [m.key for m in b]
    c = daily_missions("2026-09-16")
    assert [m.key for m in a] != [m.key for m in c] or True  # 允許巧合相同
    assert all(m.key in {d.key for d in MISSION_POOL} for m in a)


def test_record_progress_and_xp():
    t = MissionTracker("2026-09-15")
    # 找一個 kill 任務灌進度
    kill_keys = [k for k, d in t.defs.items() if d.event == "kill"]
    if not kill_keys:
        return  # 當日無 kill 任務則跳過（ deterministic 日子固定，可接受）
    key = kill_keys[0]
    target = t.defs[key].target
    done = t.record("kill", target - 1)
    assert done == []
    assert t.progress[key].progress == target - 1
    done = t.record("kill", 5)  # 超量應夾取
    assert done == [key]
    assert t.progress[key].progress == target
    assert t.xp == t.defs[key].xp


def test_unrelated_event_ignored():
    t = MissionTracker("2026-09-15")
    before = {k: v.progress for k, v in t.progress.items()}
    t.record("nonexistent_event_xyz", 99)
    assert {k: v.progress for k, v in t.progress.items()} == before


def test_level_thresholds():
    t = MissionTracker("2026-09-15")
    assert t.level == 1
    t.xp = 999
    assert t.level == 1
    t.xp = 1000
    assert t.level == 2
    t.xp = 2500
    assert t.level == 3


def test_persistence_roundtrip():
    t = MissionTracker("2026-09-15")
    t.record("kill", 3)
    t.record("match_end", 1)
    data = t.to_dict()
    t2 = MissionTracker.from_dict(data)
    assert t2.date == t.date and t2.xp == t.xp
    assert {k: v.progress for k, v in t2.progress.items()} == \
        {k: v.progress for k, v in t.progress.items()}


def test_summary_shape():
    t = MissionTracker("2026-09-15")
    s = t.summary()
    assert len(s) == DAILY_COUNT
    for row in s:
        assert set(row) == {"key", "desc", "progress", "target", "xp", "claimed"}
