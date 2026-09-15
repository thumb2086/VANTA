"""tests/test_fun_client_e2e.py — 任務可玩＋回放可播 冒煙測試
對應本 goal 停止條件 2/3：mission_ui / replay_viewer 與 server 對接
不啟動 Godot，僅驗證對應的 Python 層邏輯與檔案格式相容性。
"""

import os
import tempfile
from server.game.missions import MissionTracker
from server.game.replay import ReplayRecorder, ReplayPlayer
from server.core.movement import MoveInput
from server.game.entities import World


def test_mission_ui_persistence_via_dict():
    t = MissionTracker("2026-09-15")
    t.record("kill", 10)
    d = t.to_dict()
    assert "date" in d and "progress" in d and "xp" in d
    # 模擬 client mission_ui.save/load：JSON round-trip
    import json
    s = json.dumps(d)
    d2 = json.loads(s)
    t2 = MissionTracker.from_dict(d2)
    assert t2.xp == t.xp
    assert {k: v.progress for k, v in t2.progress.items()} == {k: v.progress for k, v in t.progress.items()}


def test_mission_xp_level_progression():
    t = MissionTracker("2026-09-16")
    lvl0 = t.level
    # 找一個 kill 任務灌滿
    kill_keys = [k for k, df in t.defs.items() if df.event == "kill"]
    if kill_keys:
        k = kill_keys[0]
        t.record("kill", t.defs[k].target)
        assert t.level >= lvl0
        assert t.xp == t.defs[k].xp


def test_replay_viewer_file_format_compatible():
    w = World()
    m = w.start_match(mode="competitive")
    rec = ReplayRecorder()
    rec.record_meta("viewer_test", "competitive", "default")
    for _ in range(32):
        w.step([MoveInput() for _ in w.players], 1.0/128.0)
        rec.record_tick(w.tick, w.time, w)
    rec.record_event(w.tick, "kill", {"killer": 0, "victim": 5, "weapon": "vandal"})
    rec.finish(0, {0:1, 1:0})
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rep")
        rec.save(path)
        # 驗證檔案存在且可被 viewer 格式解析（JSONL）
        assert os.path.isfile(os.path.join(path, "meta.json"))
        assert os.path.isfile(os.path.join(path, "ticks.jsonl"))
        assert os.path.isfile(os.path.join(path, "events.jsonl"))
        pl = ReplayPlayer()
        pl.load(path)
        assert pl.state_at(pl.ticks[-1]["tick"]) is not None
        assert len(pl.events_between(0, 10**9)) >= 1
        assert pl.jump_to_event("kill") is not None


def test_tdm_weapon_ladder_progression():
    from server.game.modes import tdm_next_weapon, TDM_LADDER
    assert tdm_next_weapon(0) == TDM_LADDER[0]
    assert tdm_next_weapon(3) == TDM_LADDER[1]
    assert tdm_next_weapon(100) == TDM_LADDER[-1]


def test_client_hud_event_codes_exist():
    # 確保 net_client.gd 與 protocol.py 的 EV_* 一致
    import pathlib
    proto = pathlib.Path("server/netcode/protocol.py").read_text(encoding="utf-8")
    gd = pathlib.Path("client/scripts/net_client.gd").read_text(encoding="utf-8")
    for code in ("EV_ASSIST", "EV_STREAK", "EV_CLUTCH", "EV_ORB"):
        assert code in proto, code
        assert code in gd, code + " missing in net_client.gd"
